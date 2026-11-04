package com.ragenthub.entity;

import jakarta.persistence.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "audit_log")
public class AuditLog {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String username;
    private String domain;
    @Column(length = 4000)
    private String question;
    @Column(length = 8000)
    private String answer;
    private String guardAction;
    private Integer latencyMs;
    private LocalDateTime createdAt = LocalDateTime.now();
}
