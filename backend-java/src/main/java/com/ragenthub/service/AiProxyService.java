package com.ragenthub.service;

import com.ragenthub.entity.AuditLog;
import com.ragenthub.repository.AuditLogRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 调用 Python AI 服务，并在 Java 侧落一份审计（双写，便于后端自己做报表）。
 */
@Service
@RequiredArgsConstructor
public class AiProxyService {

    private final org.springframework.web.client.RestClient aiRestClient;
    private final AuditLogRepository auditLogRepository;

    public Map<String, Object> chat(String username, String domain, String question) {
        long t0 = System.currentTimeMillis();

        @SuppressWarnings("unchecked")
        Map<String, Object> resp = aiRestClient.post()
                .uri("/api/v1/chat")
                .body(Map.of(
                        "question", question,
                        "domain", domain,
                        "user_id", username
                ))
                .retrieve()
                .body(Map.class);

        long latency = System.currentTimeMillis() - t0;

        AuditLog log = new AuditLog();
        log.setUsername(username);
        log.setDomain(domain);
        log.setQuestion(question);
        log.setAnswer(resp == null ? "" : String.valueOf(resp.get("answer")));
        if (resp != null && resp.get("agent_trace") instanceof Map<?, ?> trace) {
            log.setGuardAction(String.valueOf(trace.get("guard_action")));
        }
        log.setLatencyMs((int) latency);
        auditLogRepository.save(log);

        return resp;
    }

    public List<AuditLog> recentAudits() {
        return auditLogRepository.findTop50ByOrderByCreatedAtDesc();
    }
}
