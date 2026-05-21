import React, { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, Select, message, Space, Table, Tag } from 'antd';
import { PlusOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons';

const { Option } = Select;

interface AddStockFormData {
  symbol: string;
  name: string;
  market: string;
  industry?: string;
  sector?: string;
  list_date?: string;
}

interface DownloadKlinesFormData {
  symbols: string[];
  period: string;
  days: number;
}

interface Stock {
  symbol: string;
  name: string;
  market: string;
  industry?: string;
  sector?: string;
  list_date?: string;
}

const StockManagement: React.FC = () => {
  const [addStockModalVisible, setAddStockModalVisible] = useState(false);
  const [downloadModalVisible, setDownloadModalVisible] = useState(false);
  const [addStockForm] = Form.useForm();
  const [downloadForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [downloadResults, setDownloadResults] = useState<any[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [stocksLoading, setStocksLoading] = useState(false);

  // 加载股票列表
  const fetchStocks = async () => {
    setStocksLoading(true);
    try {
      const response = await fetch('/api/stocks/data-status?page=1&pageSize=100');
      const result = await response.json();
      if (result.stocks) {
        setStocks(result.stocks);
      }
    } catch (error) {
      message.error('加载股票列表失败');
    } finally {
      setStocksLoading(false);
    }
  };

  // 组件加载时获取股票列表
  useEffect(() => {
    fetchStocks();
  }, []);

  const handleAddStock = async (values: AddStockFormData) => {
    setLoading(true);
    try {
      const response = await fetch('/api/stocks/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      const result = await response.json();

      if (result.success) {
        message.success(result.message);
        setAddStockModalVisible(false);
        addStockForm.resetFields();
        fetchStocks(); // 刷新股票列表
      } else {
        message.error(result.error || '添加失败');
      }
    } catch (error) {
      message.error('网络错误');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadKlines = async (values: DownloadKlinesFormData) => {
    setLoading(true);
    try {
      const symbols = values.symbols.split(/[,，\s]+/).filter(s => s.trim());
      const response = await fetch('/api/data/download-klines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols,
          period: values.period,
          days: values.days,
        }),
      });
      const result = await response.json();

      // 调试：打印完整的API响应
      console.log('=== 下载API响应 ===', result);
      console.log('total_rows:', result.total_rows);
      console.log('succeeded:', result.succeeded);

      if (result.success) {
        const symbolCount = symbols.length;
        const rowsInfo = result.total_rows ? `，共 ${result.total_rows} 条K线数据` : '';
        const totalMsg = `下载完成：${symbolCount}只股票，成功 ${result.succeeded}，失败 ${result.failed}${rowsInfo}`;

        // 显示数据源信息
        if (result.data_sources) {
          const sources = Object.keys(result.data_sources).join(', ');
          console.log(`使用的数据源: ${sources}`);
        }

        console.log('=== 显示消息 ===', totalMsg);
        message.success(totalMsg, 5);
        setDownloadResults([{
          key: Date.now(),
          period: result.period,
          total: result.total,
          succeeded: result.succeeded,
          failed: result.failed,
          failures: result.failures,
          total_rows: result.total_rows,
        }]);

        // 下载成功后刷新股票列表
        fetchStocks();
      } else {
        message.error(result.error || '下载失败');
      }
    } catch (error) {
      console.error('=== 下载错误 ===', error);
      message.error('网络错误');
    } finally {
      setLoading(false);
    }
  };

  const periodOptions = [
    { label: '日线', value: 'daily' },
    { label: '周线', value: 'weekly' },
    { label: '月线', value: 'monthly' },
    { label: '1分钟', value: '1min' },
    { label: '5分钟', value: '5min' },
    { label: '15分钟', value: '15min' },
    { label: '30分钟', value: '30min' },
    { label: '60分钟', value: '60min' },
  ];

  const stockColumns = [
    {
      title: '股票代码',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 120,
    },
    {
      title: '股票名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '市场',
      dataIndex: 'market',
      key: 'market',
      width: 80,
      render: (market: string) => (
        <Tag color={market === 'A' ? 'blue' : 'green'}>{market}</Tag>
      ),
    },
    {
      title: 'K线数据',
      dataIndex: 'kline_days',
      key: 'kline_days',
      width: 100,
      render: (days: number) => days ? `${days}天` : '-',
    },
    {
      title: '因子数据',
      dataIndex: 'factor_count',
      key: 'factor_count',
      width: 100,
      render: (count: number) => count ? `${count}个` : '-',
    },
    {
      title: '数据完整',
      dataIndex: 'data_complete',
      key: 'data_complete',
      width: 100,
      render: (complete: boolean) => (
        <Tag color={complete ? 'green' : 'orange'}>
          {complete ? '完整' : '不完整'}
        </Tag>
      ),
    },
  ];

  const resultColumns = [
    {
      title: '周期',
      dataIndex: 'period',
      key: 'period',
      render: (period: string) => {
        const periodMap: Record<string, string> = {
          daily: '日线',
          weekly: '周线',
          monthly: '月线',
          '1min': '1分钟',
          '5min': '5分钟',
          '15min': '15分钟',
          '30min': '30分钟',
          '60min': '60分钟',
        };
        return <Tag color="blue">{periodMap[period] || period}</Tag>;
      },
    },
    {
      title: '总数',
      dataIndex: 'total',
      key: 'total',
    },
    {
      title: '成功',
      dataIndex: 'succeeded',
      key: 'succeeded',
      render: (count: number) => <Tag color="green">{count}</Tag>,
    },
    {
      title: '失败',
      dataIndex: 'failed',
      key: 'failed',
      render: (count: number) => count > 0 ? <Tag color="red">{count}</Tag> : <Tag>{count}</Tag>,
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card title="股票管理" extra={
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchStocks}
            loading={stocksLoading}
          >
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddStockModalVisible(true)}
          >
            添加股票
          </Button>
          <Button
            type="default"
            icon={<DownloadOutlined />}
            onClick={() => setDownloadModalVisible(true)}
          >
            下载数据
          </Button>
        </Space>
      }>
        <div style={{ marginBottom: 16 }}>
          <h3>股票列表</h3>
          <Table
            columns={stockColumns}
            dataSource={stocks}
            rowKey="symbol"
            loading={stocksLoading}
            pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 只股票` }}
            size="small"
          />
        </div>

        {downloadResults.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h3>下载结果</h3>
            <Table
              columns={resultColumns}
              dataSource={downloadResults}
              pagination={false}
              size="small"
            />
          </div>
        )}
      </Card>

      {/* 添加股票弹窗 */}
      <Modal
        title="添加股票"
        open={addStockModalVisible}
        onCancel={() => setAddStockModalVisible(false)}
        footer={null}
      >
        <Form
          form={addStockForm}
          layout="vertical"
          onFinish={handleAddStock}
        >
          <Form.Item
            label="股票代码"
            name="symbol"
            rules={[{ required: true, message: '请输入股票代码' }]}
          >
            <Input placeholder="例如：600519" />
          </Form.Item>

          <Form.Item
            label="股票名称"
            name="name"
            rules={[{ required: true, message: '请输入股票名称' }]}
          >
            <Input placeholder="例如：贵州茅台" />
          </Form.Item>

          <Form.Item
            label="市场"
            name="market"
            rules={[{ required: true, message: '请选择市场' }]}
          >
            <Select placeholder="选择市场">
              <Option value="A">A股</Option>
              <Option value="HK">港股</Option>
            </Select>
          </Form.Item>

          <Form.Item label="行业" name="industry">
            <Input placeholder="例如：白酒" />
          </Form.Item>

          <Form.Item label="板块" name="sector">
            <Input placeholder="例如：主板" />
          </Form.Item>

          <Form.Item label="上市日期" name="list_date">
            <Input placeholder="格式：YYYY-MM-DD" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                添加
              </Button>
              <Button onClick={() => setAddStockModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 下载K线数据弹窗 */}
      <Modal
        title="下载K线数据"
        open={downloadModalVisible}
        onCancel={() => setDownloadModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={downloadForm}
          layout="vertical"
          onFinish={handleDownloadKlines}
          initialValues={{ period: 'daily', days: 730 }}
        >
          <Form.Item
            label="股票代码"
            name="symbols"
            rules={[{ required: true, message: '请输入股票代码' }]}
            extra="多个股票用逗号或空格分隔，例如：600519, 000001, 600036"
          >
            <Input.TextArea
              rows={3}
              placeholder="例如：600519, 000001, 600036"
            />
          </Form.Item>

          <Form.Item
            label="K线周期"
            name="period"
            rules={[{ required: true, message: '请选择K线周期' }]}
          >
            <Select>
              {periodOptions.map(opt => (
                <Option key={opt.value} value={opt.value}>{opt.label}</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="下载天数"
            name="days"
            rules={[{ required: true, message: '请输入下载天数' }]}
            extra="日/周/月线建议730天，分钟线建议5-8天"
          >
            <Input type="number" placeholder="例如：730" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                开始下载
              </Button>
              <Button onClick={() => setDownloadModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StockManagement;
