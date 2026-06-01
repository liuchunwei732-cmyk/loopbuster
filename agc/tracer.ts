import { trace, Span } from '@opentelemetry/api';

export class AuditTracer {
  static startSpan(name: string, attributes: Record<string, any>) {
    const tracer = trace.getTracer('agc-governance');
    return tracer.startSpan(name, { attributes });
  }

  static recordFailure(span: Span, error: Error) {
    span.setStatus({ code: 1, message: error.message });
    span.recordException(error);
    span.end();
  }
}
