export class SkillExecutor {
  async executeWithRetry(fn: () => Promise<any>, retries = 3, backoff = 1000): Promise<any> {
    try {
      return await fn();
    } catch (error) {
      if (retries <= 0) throw error;
      console.warn(`Retry attempt, remaining: ${retries}, waiting ${backoff}ms`);
      await new Promise(resolve => setTimeout(resolve, backoff));
      return this.executeWithRetry(fn, retries - 1, backoff * 2);
    }
  }
}
