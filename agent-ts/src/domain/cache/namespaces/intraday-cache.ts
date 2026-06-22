import { BaseNamespace } from './base-namespace.js';
import { getNamespaceConfig } from '../core/cache-config.js';

export class IntradayCache extends BaseNamespace {
  constructor() {
    super(getNamespaceConfig('intraday'));
  }
}
