import { BaseNamespace } from './base-namespace.js';
import { getNamespaceConfig } from '../core/cache-config.js';

export class QuarterlyCache extends BaseNamespace {
  constructor() {
    super(getNamespaceConfig('quarterly'));
  }
}
