/**
 * Browser Tool - 浏览器操作工具
 */
import { Type } from "@sinclair/typebox";
import { chromium, type Browser, type Page } from "playwright";
import { mkdirSync } from "fs";
import { writeFile } from "fs/promises";
import { join } from "path";

let browser: Browser | null = null;
let page: Page | null = null;
let screenshotsDir = "screenshots";

// 随机延迟，模拟人类操作
function randomDelay(min = 500, max = 1500): Promise<void> {
  const delay = Math.floor(Math.random() * (max - min + 1)) + min;
  return new Promise(resolve => setTimeout(resolve, delay));
}

export function initBrowserTool(sessionDir: string) {
  screenshotsDir = join(sessionDir, "screenshots");
  mkdirSync(screenshotsDir, { recursive: true });
}

async function getBrowser() {
  if (!browser) {
    browser = await chromium.launch({
      headless: false, // 使用有头模式，更难被检测
      args: [
        '--disable-blink-features=AutomationControlled', // 隐藏自动化特征
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process'
      ]
    });
  }
  return browser;
}

async function getPage() {
  if (!page || page.isClosed()) {
    const b = await getBrowser();
    page = await b.newPage();

    // 设置视口大小（模拟真实桌面浏览器）
    await page.setViewportSize({ width: 1920, height: 1080 });

    // 设置真实的 User-Agent
    await page.setExtraHTTPHeaders({
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Encoding': 'gzip, deflate, br',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1'
    });

    // 注入脚本隐藏 webdriver 特征
    await page.addInitScript(`
      // 删除 navigator.webdriver
      Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
      });

      // 伪造 Chrome 对象
      window.chrome = {
        runtime: {}
      };

      // 伪造 permissions
      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
          Promise.resolve({ state: window.Notification.permission }) :
          originalQuery(parameters)
      );

      // 伪造 plugins
      Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
      });

      // 伪造 languages
      Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en']
      });
    `);
  }
  return page;
}

export const browserTool = {
  name: "browser",
  label: "浏览器自动化",
  description:
    "Automate a real browser to retrieve live information or interact with web pages. " +
    "Use when you need real-time data (flights, hotels, news, prices) or must fill forms, click buttons, or extract page content that cannot be fetched otherwise. " +
    "Do NOT use for static pages accessible via fetch or web search — browser automation is slower and heavier. " +
    "Action reference: " +
    "connect (attach to an existing Chrome at a CDP URL, e.g. http://localhost:9222 — do this first if user has a browser open), " +
    "navigate (go to URL; always navigate before interacting), " +
    "click (click a CSS selector; use after navigate), " +
    "fill (type into a field identified by CSS selector), " +
    "getText (extract visible text from a selector; saves to file if >1000 chars), " +
    "getHTML (get full page HTML; always saves to file), " +
    "screenshot (capture current page; use to verify state or share what you see), " +
    "close (shut down browser when done — always call this when finished), " +
    "search (search Bing with a query string and return results — the fastest way to look up real-time info, use this instead of manually navigating to a search engine).",
  parameters: Type.Object({
    action: Type.String({ description: "Action to perform: search | navigate | click | fill | getText | getHTML | screenshot | connect | close" }),
    url: Type.Optional(Type.String({ description: "URL to navigate to (for navigate), or CDP endpoint to attach to (for connect, e.g. http://localhost:9222)" })),
    selector: Type.Optional(Type.String({ description: "CSS selector for the target element (used with click, fill, getText)" })),
    text: Type.Optional(Type.String({ description: "Search query (for search) or text to type into a field (for fill)" })),
    path: Type.Optional(Type.String({ description: "File path to save screenshot (optional — defaults to session screenshots directory)" }))
  }),
  execute: async (_toolCallId: string, params: {
    action: string;
    url?: string;
    selector?: string;
    text?: string;
    path?: string;
  }) => {
    try {
      const p = await getPage();
      let result = "";

      switch (params.action) {
        case "connect":
          // 连接到现有浏览器实例
          const cdpUrl = params.url || "http://localhost:9222";

          try {
            // 关闭之前的连接
            if (page) await page.close();
            if (browser) await browser.close();

            // 连接到现有浏览器
            browser = await chromium.connectOverCDP(cdpUrl);
            const contexts = browser.contexts();

            if (contexts.length === 0) {
              throw new Error("未找到浏览器上下文，请确保浏览器已启动");
            }

            // 获取第一个上下文的第一个页面
            const context = contexts[0];
            const pages = context.pages();

            if (pages.length === 0) {
              throw new Error("未找到打开的标签页");
            }

            page = pages[0];
            const currentUrl = page.url();
            const title = await page.title();

            result = `已连接到浏览器\n- CDP地址: ${cdpUrl}\n- 当前页面: ${title}\n- URL: ${currentUrl}\n- 打开的标签页数: ${pages.length}`;
          } catch (error) {
            throw new Error(`连接失败: ${error instanceof Error ? error.message : String(error)}\n\n提示：\n1. Chrome需要以调试模式启动: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222\n2. 或使用默认端口: http://localhost:9222`);
          }
          break;

        case "navigate": {
          if (!params.url) throw new Error("navigate需要url参数");
          await p.goto(params.url, { waitUntil: 'domcontentloaded', timeout: 15000 });
          await randomDelay(500, 1000);
          const navTitle = await p.title();
          const navText = (await p.textContent('body') || '').replace(/\s+/g, ' ').trim();
          const navPreview = navText.substring(0, 2000);
          result = `已导航到: ${params.url}\n标题: ${navTitle}\n\n页面内容:\n${navPreview}${navText.length > 2000 ? `\n\n[已截断，共 ${navText.length} 字符，可用 getText 获取更多]` : ''}`;
          break;
        }

        case "search": {
          if (!params.text) throw new Error("search需要text参数");
          const searchUrl = `https://www.bing.com/search?q=${encodeURIComponent(params.text)}&setlang=zh-CN`;
          await p.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
          await randomDelay(500, 1000);
          // 提取搜索结果文本（去掉导航栏等噪声）
          const searchText = (await p.textContent('#b_results, main, body') || '').replace(/\s+/g, ' ').trim();
          result = `搜索"${params.text}"结果:\n\n${searchText.substring(0, 3000)}${searchText.length > 3000 ? `\n\n[已截断，共 ${searchText.length} 字符]` : ''}`;
          break;
        }

        case "click":
          if (!params.selector) throw new Error("click需要selector参数");
          await randomDelay(); // 模拟思考时间
          await p.click(params.selector);
          await randomDelay(500, 1000); // 等待响应
          result = `已点击: ${params.selector}`;
          break;

        case "fill":
          if (!params.selector || !params.text) throw new Error("fill需要selector和text参数");
          await randomDelay();
          await p.click(params.selector); // 先点击聚焦
          await randomDelay(200, 500);
          await p.fill(params.selector, params.text, { timeout: 5000 });
          await randomDelay(300, 600);
          result = `已填写: ${params.selector} = ${params.text}`;
          break;

        case "getText":
          if (!params.selector) throw new Error("getText需要selector参数");
          const text = await p.textContent(params.selector);

          if (!text) {
            result = "未找到内容";
          } else if (text.length <= 1000) {
            // 内容较短，直接返回
            result = text;
          } else {
            // 内容过长，保存到文件
            const contentFile = join(screenshotsDir, `page-content-${Date.now()}.md`);
            const currentUrl = p.url();
            const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

            const mdContent = `# 页面内容

**URL**: ${currentUrl}
**抓取时间**: ${timestamp}
**选择器**: ${params.selector}
**内容长度**: ${text.length} 字符

---

${text}
`;
            await writeFile(contentFile, mdContent, 'utf-8');

            // 只返回摘要信息
            const preview = text.substring(0, 500);
            result = `页面内容已保存到: ${contentFile}\n\n内容预览 (前500字符):\n${preview}...\n\n[总长度: ${text.length} 字符，完整内容见文件。使用 read 工具查看完整内容]`;
          }
          break;

        case "getHTML":
          const html = await p.content();
          const htmlFile = join(screenshotsDir, `page-html-${Date.now()}.html`);
          const currentUrl = p.url();
          const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);

          await writeFile(htmlFile, html, 'utf-8');

          // 提取关键信息
          const title = await p.title();
          const htmlPreview = html.substring(0, 500);

          result = `页面HTML已保存到: ${htmlFile}\n\n页面信息:\n- URL: ${currentUrl}\n- 标题: ${title}\n- 抓取时间: ${timestamp}\n- HTML长度: ${html.length} 字符\n\nHTML预览 (前500字符):\n${htmlPreview}...\n\n[使用 read 工具查看完整HTML]`;
          break;

        case "screenshot":
          const screenshotPath = params.path || join(screenshotsDir, `screenshot-${Date.now()}.png`);
          await p.screenshot({ path: screenshotPath });
          result = `截图已保存: ${screenshotPath}`;
          break;

        case "close":
          if (page) await page.close();
          if (browser) await browser.close();
          page = null;
          browser = null;
          result = "浏览器已关闭";
          break;

        default:
          throw new Error(`未知操作: ${params.action}`);
      }

      return {
        content: [{ type: "text" as const, text: result }],
        details: { action: params.action }
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `浏览器操作失败: ${errorMsg}` }],
        details: { action: params.action, error: errorMsg }
      };
    }
  }
};
