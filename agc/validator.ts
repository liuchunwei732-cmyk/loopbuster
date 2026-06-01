import { z } from 'zod';

export const SkillSchema = z.object({
  name: z.string(),
  version: z.string(),
  description: z.string(),
  parameters: z.record(z.any()),
  execute: z.function(),
});

export type Skill = z.infer<typeof SkillSchema>;

export class SkillValidator {
  validate(skill: any) {
    return SkillSchema.parse(skill);
  }
}
