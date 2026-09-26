package com.aegle.security;

import com.aegle.config.AegleProperties;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Caps request rates on /api per signed-in user (per client IP before authentication), with
 * a tighter separate limit on uploads. Runs after token authentication so it can key on the
 * user. Limits are shared across API instances (see {@link RateLimiter}). Over the limit:
 * 429 with Retry-After.
 */
public class RateLimitFilter extends OncePerRequestFilter {

    private final RateLimiter limiter;
    private final AegleProperties.RateLimit cfg;

    public RateLimitFilter(RateLimiter limiter, AegleProperties.RateLimit cfg) {
        this.limiter = limiter;
        this.cfg = cfg;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String key = callerKey(request);
        long wait = limiter.tryAcquire("requests", key, cfg.requestsPerMinute());
        if (wait == 0 && isUpload(request)) {
            wait = limiter.tryAcquire("uploads", key, cfg.uploadsPerMinute());
        }
        if (wait > 0) {
            response.setStatus(429);
            response.setHeader(HttpHeaders.RETRY_AFTER, Long.toString(wait));
            response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
            response.getWriter().write(
                    "{\"type\":\"about:blank\",\"title\":\"Too Many Requests\",\"status\":429,"
                            + "\"detail\":\"Too many requests, retry later\"}");
            return;
        }
        chain.doFilter(request, response);
    }

    private static String callerKey(HttpServletRequest request) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth instanceof JwtAuthenticationToken jwt) {
            return "user:" + jwt.getToken().getSubject();
        }
        return "ip:" + request.getRemoteAddr();
    }

    private static boolean isUpload(HttpServletRequest request) {
        return "POST".equals(request.getMethod()) && "/api/studies".equals(request.getRequestURI());
    }
}
