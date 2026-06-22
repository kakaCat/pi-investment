import { BaseNamespace } from './base-namespace.js';
import { getNamespaceConfig } from '../core/cache-config.js';

export class DailyCache extends BaseNamespace {
  constructor() {
    super(getNamespaceConfig('daily'));
  }
}
