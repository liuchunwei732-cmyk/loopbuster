import { Skill } from './validator';

export class SkillRegistry {
  private skills = new Map<string, Skill>();

  register(skill: Skill) {
    this.skills.set(`${skill.name}@${skill.version}`, skill);
  }

  get(name: string, version: string) {
    return this.skills.get(`${name}@${version}`);
  }
}
