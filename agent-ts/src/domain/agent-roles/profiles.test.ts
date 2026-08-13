import { describe, test, expect } from '@jest/globals';
import { ROLE_PROFILES, getProfile } from './profiles.js';
import type { AgentKind } from './types.js';

describe('Agent Role Profiles', () => {
  test('fin profile has correct configuration', () => {
    const profile = ROLE_PROFILES.fin;
    expect(profile.kind).toBe('fin');
    expect(profile.toolGroup).toBe('FIN');
    expect(profile.modelPreference).toBe('inherit');
    expect(profile.promptVariant).toBe('fin');
    expect(profile.memoryWriteScopes).toEqual(['daily', 'experience', 'watch', 'portfolio', 'global']);
  });

  test('evolution profile has correct configuration', () => {
    const profile = ROLE_PROFILES.evolution;
    expect(profile.kind).toBe('evolution');
    expect(profile.toolGroup).toBe('EVOLUTION');
    expect(profile.modelPreference).toBe('pro');
    expect(profile.promptVariant).toBe('evolution');
    expect(profile.memoryWriteScopes).toEqual(['evolution']);
  });

  test('memory profile has correct configuration', () => {
    const profile = ROLE_PROFILES.memory;
    expect(profile.kind).toBe('memory');
    expect(profile.toolGroup).toBe('MEMORY');
    expect(profile.modelPreference).toBe('flash');
    expect(profile.promptVariant).toBe('memory');
    expect(profile.memoryWriteScopes).toEqual(['memory', 'recall-audit']);
  });

  test('getProfile returns correct profile for valid kind', () => {
    expect(getProfile('fin').kind).toBe('fin');
    expect(getProfile('evolution').kind).toBe('evolution');
    expect(getProfile('memory').kind).toBe('memory');
  });

  test('getProfile throws error for invalid kind', () => {
    expect(() => getProfile('invalid' as AgentKind)).toThrow('unknown agent kind: invalid');
  });

  test('all profiles have required fields', () => {
    const kinds: AgentKind[] = ['fin', 'evolution', 'memory'];
    kinds.forEach(kind => {
      const profile = ROLE_PROFILES[kind];
      expect(profile.kind).toBe(kind);
      expect(typeof profile.promptVariant).toBe('string');
      expect(['FIN', 'EVOLUTION', 'MEMORY']).toContain(profile.toolGroup);
      expect(['flash', 'pro', 'inherit']).toContain(profile.modelPreference);
      expect(Array.isArray(profile.memoryWriteScopes)).toBe(true);
    });
  });
});
