import sqlite3 from 'better-sqlite3';

export class TaskStorage {
  private db: any;

  constructor(path: string = 'agc.db') {
    this.db = sqlite3(path);
    // 开启WAL模式以支持并发读取和写入
    this.db.pragma('journal_mode = WAL');
    this.init();
  }

  private init() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        intent TEXT,
        status TEXT,
        payload TEXT,
        result TEXT,
        error TEXT,
        checkpoint INTEGER,
        version INTEGER DEFAULT 0
      )
    `);
  }

  // 幂等更新：只有版本号更新或初始插入才生效
  saveTask(task: any) {
    const transaction = this.db.transaction((t: any) => {
      const existing = this.db.prepare('SELECT version FROM tasks WHERE id = ?').get(t.id);
      if (existing && t.version <= existing.version) return; // 幂等检查

      const stmt = this.db.prepare(`
        INSERT OR REPLACE INTO tasks (id, intent, status, payload, result, error, checkpoint, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `);
      stmt.run(t.id, t.intent, t.status, JSON.stringify(t.payload), 
               JSON.stringify(t.result), t.error, t.checkpoint, t.version || 0);
    });
    transaction(task);
  }
}
