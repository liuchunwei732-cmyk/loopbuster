import Redis from 'ioredis';

export interface IStateBackend {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, ttl?: number): Promise<void>;
  lock(key: string, ttl: number): Promise<boolean>;
}

export class RedisBackend implements IStateBackend {
  private redis: Redis;

  constructor(url: string) {
    this.redis = new Redis(url);
  }

  async get(key: string) { return await this.redis.get(key); }
  async set(key: string, value: string, ttl?: number) {
    if (ttl) await this.redis.set(key, value, 'EX', ttl);
    else await this.redis.set(key, value);
  }
  async lock(key: string, ttl: number) {
    const result = await this.redis.set(`${key}:lock`, '1', 'NX', 'EX', ttl);
    return result === 'OK';
  }
}
