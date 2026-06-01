export class AuditLogger {
  private taskId: string;

  constructor(taskId: string) {
    this.taskId = taskId;
  }

  log(action: string, metadata: any = {}) {
    const entry = {
      timestamp: new Date().toISOString(),
      taskId: this.taskId,
      action,
      ...metadata
    };
    console.log(JSON.stringify(entry));
  }
}
