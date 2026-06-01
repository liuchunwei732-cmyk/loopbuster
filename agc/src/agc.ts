import { z } from 'zod';
import { IStateBackend } from './backend';
import { AuditTracer } from './tracer';
import { Middleware } from './middleware';

export class AGCCore {
  private registry: Map<string, any> = new Map();
  private middlewares: Middleware[] = [];

  constructor(private config: { storage: IStateBackend }) {}

  registerSkill(name: string, skill: { schema: z.ZodSchema, handler: Function }) {
    this.registry.set(name, skill);
  }

  use(middleware: Middleware) {
    this.middlewares.push(middleware);
  }

  async execute(skillName: string, data: any) {
    const span = AuditTracer.startSpan('execute', { skillName });
    try {
      const skill = this.registry.get(skillName);
      if (!skill) throw new Error('Skill not found');
      
      skill.schema.parse(data);
      
      let index = 0;
      const next = async () => {
        if (index < this.middlewares.length) {
          await this.middlewares[index++].execute(data, next);
        } else {
          await skill.handler(data);
        }
      };
      
      await next();
      span.end();
    } catch (e: any) {
      AuditTracer.recordFailure(span, e);
      throw e;
    }
  }
}
