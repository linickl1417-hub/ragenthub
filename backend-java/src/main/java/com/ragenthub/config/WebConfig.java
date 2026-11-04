package com.ragenthub.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestClient;

@Configuration
public class WebConfig {

    @Value("${ai.service.base-url}")
    private String aiBaseUrl;

    @Bean
    public RestClient aiRestClient(RestClient.Builder builder) {
        return builder.baseUrl(aiBaseUrl).build();
    }
}
