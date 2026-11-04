package com.ragenthub.controller;

import com.ragenthub.entity.AuditLog;
import com.ragenthub.service.AiProxyService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class ChatController {

    private final AiProxyService aiProxyService;

    @PostMapping("/chat")
    public Map<String, Object> chat(
            Authentication auth,
            @RequestBody Map<String, String> body
    ) {
        return aiProxyService.chat(
                auth.getName(),
                body.getOrDefault("domain", "medical"),
                body.get("question")
        );
    }

    @GetMapping("/audit/recent")
    public List<AuditLog> recent() {
        return aiProxyService.recentAudits();
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("status", "ok", "service", "backend-java");
    }
}
