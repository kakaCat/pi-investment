/**
 * Monitor Alert Tool Tests
 */
import { describe, it, expect } from '@jest/globals';
import { monitorAlertTool } from './alert-tool.js';

describe('monitorAlertTool', () => {
  it('should have correct tool name', () => {
    expect(monitorAlertTool.name).toBe('monitor_alert');
  });

  it('should have correct label', () => {
    expect(monitorAlertTool.label).toBe('监控告警');
  });

  it('should have description mentioning all notification types', () => {
    expect(monitorAlertTool.description).toContain('general');
    expect(monitorAlertTool.description).toContain('trade_signal');
    expect(monitorAlertTool.description).toContain('market_brief');
    expect(monitorAlertTool.description).toContain('risk_warning');
  });

  it('should have parameters object', () => {
    expect(monitorAlertTool.parameters).toBeDefined();
    expect(typeof monitorAlertTool.parameters).toBe('object');
  });

  it('should have execute function', () => {
    expect(monitorAlertTool.execute).toBeDefined();
    expect(typeof monitorAlertTool.execute).toBe('function');
  });

  it('should have type parameter with all notification types', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties).toBeDefined();
    expect(params.properties.type).toBeDefined();
  });

  it('should support general notification parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.message).toBeDefined();
    expect(params.properties.title).toBeDefined();
  });

  it('should support trade signal parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.action).toBeDefined();
    expect(params.properties.symbol).toBeDefined();
    expect(params.properties.confidence).toBeDefined();
  });

  it('should support market brief parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.summary).toBeDefined();
    expect(params.properties.indices).toBeDefined();
  });

  it('should support risk warning parameters', () => {
    const params = monitorAlertTool.parameters as any;
    expect(params.properties.warning).toBeDefined();
    expect(params.properties.severity).toBeDefined();
  });
});
