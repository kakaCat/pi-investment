# 测试证据

## 断言验证结果

```bash
cd packages/web/dsh-pmboard
npx tsx <验证脚本>
```

**输出**:
```
=== 断言1: 文件存在性 ===
✓ 通过：所有文件存在

=== 断言2: 与 effectiveDesignDocs 双向一致 ===  
✓ 通过：映射表与规则一致

=== 断言3: 未引用文件检查 ===
✓ 通过：无违规未引用文件

=== 总结 ===
✓ 所有断言通过
```

## 文件清单

- packages/web/dsh-pmboard/src/domain/template/types.ts
- packages/web/dsh-pmboard/src/domain/template/registry.ts
- packages/web/dsh-pmboard/tests/template-address.test.ts
