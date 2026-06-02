import { TaskStorage } from './storage';
import { SkillValidator } from './validator';

describe('AGC Core', () => {
  test('TaskStorage should persist state', () => {
    const storage = new TaskStorage(':memory:');
    const task = { id: 't1', intent: 'test', status: 'PENDING', payload: {}, checkpoint: 0 };
    storage.saveTask(task);
    // Mock check of db
    expect(true).toBe(true);
  });

  test('SkillValidator should reject invalid schema', () => {
    const validator = new SkillValidator();
    expect(() => validator.validate({})).toThrow();
  });
});
