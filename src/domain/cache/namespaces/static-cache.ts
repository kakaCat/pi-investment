import { BaseNamespace } from './base-namespace.js';
import { getNamespaceConfig } from '../core/cache-config.js';

export class StaticCache extends BaseNamespace {
  constructor() {
    super(getNamespaceConfig('static'));
  }
}
