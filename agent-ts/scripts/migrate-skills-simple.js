#!/usr/bin/env node
/**
 * Simple Skills Migration Script (Pure Node.js)
 *
 * Migrates skills from local files to Agent OS
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SKILLS_DIR = path.join(__dirname, '../skills');
const AGENT_OS_URL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';

/**
 * Parse frontmatter from markdown
 */
function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]+?)\n---\n([\s\S]*)$/);
  if (!match) {
    return { metadata: {}, content };
  }

  const [, frontmatter, body] = match;
  const metadata = {};

  frontmatter.split('\n').forEach(line => {
    const [key, ...valueParts] = line.split(':');
    if (key && valueParts.length > 0) {
      const value = valueParts.join(':').trim();
      // Remove quotes
      metadata[key.trim()] = value.replace(/^["']|["']$/g, '');
    }
  });

  return { metadata, content: body.trim() };
}

/**
 * Create skill in Agent OS
 */
async function createSkill(skillData) {
  const response = await fetch(`${AGENT_OS_URL}/api/v1/skills`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(skillData)
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`HTTP ${response.status}: ${error}`);
  }

  return response.json();
}

/**
 * Main migration function
 */
async function main() {
  console.log('🚀 Starting skills migration...\n');
  console.log(`📁 Skills directory: ${SKILLS_DIR}`);
  console.log(`🔗 Agent OS URL: ${AGENT_OS_URL}\n`);

  // Read all .md files
  const files = fs.readdirSync(SKILLS_DIR).filter(f => f.endsWith('.md'));
  console.log(`📚 Found ${files.length} skill files\n`);

  let successCount = 0;
  let skipCount = 0;
  let failCount = 0;

  for (const file of files) {
    const filePath = path.join(SKILLS_DIR, file);
    const fileContent = fs.readFileSync(filePath, 'utf-8');

    const { metadata, content } = parseFrontmatter(fileContent);

    const name = metadata.name || path.basename(file, '.md');
    const description = metadata.description || 'No description';
    const category = metadata.category || 'general';

    console.log(`📄 Processing: ${name}`);

    try {
      const skillData = {
        name,
        description,
        category,
        owner: 'fin-agent',
        content: fileContent,
        author: 'migration-script',
        metadata: {
          migrated_at: new Date().toISOString(),
          original_file: file,
          ...metadata
        }
      };

      const result = await createSkill(skillData);
      console.log(`   ✅ Created: ${result.id} (v${result.version || '1.0.0'})`);
      successCount++;
    } catch (error) {
      if (error.message.includes('409') || error.message.includes('duplicate')) {
        console.log(`   ⏭️  Skipped: Already exists`);
        skipCount++;
      } else {
        console.log(`   ❌ Failed: ${error.message}`);
        failCount++;
      }
    }
  }

  console.log('\n' + '='.repeat(50));
  console.log('📊 Migration Summary:');
  console.log(`   ✅ Created: ${successCount}`);
  console.log(`   ⏭️  Skipped: ${skipCount}`);
  console.log(`   ❌ Failed: ${failCount}`);
  console.log(`   📚 Total: ${files.length}`);
  console.log('='.repeat(50) + '\n');

  if (failCount > 0) {
    console.log('⚠️  Some skills failed to migrate. Please check the errors above.');
    process.exit(1);
  } else {
    console.log('🎉 Migration completed successfully!');
  }
}

main().catch(error => {
  console.error('❌ Migration failed:', error);
  process.exit(1);
});
