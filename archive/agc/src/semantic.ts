export class SemanticStagnationDetector {
  // 基于简单的相似度指纹进行预检，未来扩展为 Embedding 模型
  detect(history: string[], current: string): boolean {
    if (history.length < 3) return false;
    const recent = history.slice(-3);
    return recent.every(item => item === current);
  }
}
