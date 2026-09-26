package com.aegle.dicom;

import com.aegle.audit.AuditService;
import com.aegle.security.Actor;
import com.aegle.security.CurrentUserService;
import com.aegle.tenant.TenantTx;
import com.aegle.web.ConflictException;
import com.aegle.web.NotFoundException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * The DICOM senders (modalities, PACS) whose studies belong to the admin's organisation,
 * identified by calling AE title. dicom_sources has no row-level security (ingestion looks
 * it up before knowing the tenant), so every query here filters by organisation itself.
 */
@RestController
@RequestMapping("/api/admin/dicom-sources")
@Validated
@PreAuthorize("hasRole('ADMIN')")
public class DicomSourceController {

    /** DICOM AE title: 1-16 printable ASCII characters, no leading or trailing space. */
    static final String AE_TITLE = "[!-~]([ -~]{0,14}[!-~])?";

    public record Source(String aeTitle, String description, OffsetDateTime createdAt) {}

    public record NewSource(@NotNull @Pattern(regexp = AE_TITLE) String aeTitle, @Size(max = 200) String description) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final AuditService audit;

    public DicomSourceController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, AuditService audit) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.audit = audit;
    }

    @GetMapping
    public List<Source> list() {
        Actor actor = users.require();
        return jdbc.sql("SELECT ae_title, description, created_at FROM dicom_sources WHERE org_id = :org ORDER BY ae_title")
                .param("org", actor.orgId())
                .query((rs, i) -> new Source(rs.getString("ae_title"), rs.getString("description"),
                        rs.getObject("created_at", OffsetDateTime.class))).list();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Source register(@Valid @RequestBody NewSource body) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            Source created;
            try {
                created = jdbc.sql("""
                        INSERT INTO dicom_sources (ae_title, org_id, description) VALUES (:aet, :org, :desc)
                        RETURNING ae_title, description, created_at""")
                        .param("aet", body.aeTitle()).param("org", actor.orgId()).param("desc", body.description())
                        .query((rs, i) -> new Source(rs.getString("ae_title"), rs.getString("description"),
                                rs.getObject("created_at", OffsetDateTime.class))).single();
            } catch (DuplicateKeyException e) {
                throw new ConflictException("That AE title is already registered");
            }
            audit.record(actor.orgId(), actor.userId(), "DICOM_SOURCE_ADDED", "dicom_source", body.aeTitle(), Map.of());
            return created;
        });
    }

    @DeleteMapping("/{aeTitle}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void remove(@PathVariable String aeTitle) {
        Actor actor = users.require();
        tenantTx.runAs(actor.orgId(), () -> {
            int n = jdbc.sql("DELETE FROM dicom_sources WHERE ae_title = :aet AND org_id = :org")
                    .param("aet", aeTitle).param("org", actor.orgId()).update();
            if (n == 0) {
                throw new NotFoundException("dicom source");
            }
            audit.record(actor.orgId(), actor.userId(), "DICOM_SOURCE_REMOVED", "dicom_source", aeTitle, Map.of());
        });
    }
}
