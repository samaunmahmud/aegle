package com.aegle.study;

import com.aegle.security.Actor;
import com.aegle.security.ClinicianOnly;
import com.aegle.security.CurrentUserService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.io.IOException;
import java.net.URI;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/api/studies")
@Validated
@ClinicianOnly
public class StudyController {

    private final StudyService studies;
    private final CurrentUserService users;

    public StudyController(StudyService studies, CurrentUserService users) {
        this.studies = studies;
        this.users = users;
    }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<StudyService.UploadResult> upload(
            @RequestPart("file") MultipartFile file,
            @RequestParam @NotBlank @Size(max = 64) String patientMrn,
            @RequestParam(required = false) @Size(max = 200) String patientName,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate patientDob,
            @RequestParam(required = false) @Pattern(regexp = "[FMOU]") String patientSex,
            @RequestParam(defaultValue = "XR") @Pattern(regexp = "[A-Za-z]{2,3}") String modality,
            @RequestParam(defaultValue = "CHEST") @Size(max = 64) String bodyPart,
            @RequestParam(required = false) @Size(max = 64) String accessionNo,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate studyDate)
            throws IOException {
        Actor actor = users.require();
        var result = studies.upload(actor, file.getBytes(), new StudyService.UploadRequest(
                patientMrn, patientName, patientDob, patientSex, modality, bodyPart, accessionNo, studyDate));
        return ResponseEntity.created(URI.create("/api/studies/" + result.studyId())).body(result);
    }

    @GetMapping
    public List<StudyService.StudySummary> list(
            @RequestParam(required = false) @Pattern(regexp = "RECEIVED|QUEUED|ANALYZING|READY|REVIEWED|FAILED") String status,
            @RequestParam(defaultValue = "50") @Min(1) @Max(200) int limit,
            @RequestParam(defaultValue = "0") @Min(0) int offset) {
        return studies.list(users.require(), status, limit, offset);
    }

    @GetMapping("/{id}")
    public StudyService.StudyDetail detail(@PathVariable UUID id) {
        return studies.detail(users.require(), id);
    }

    @GetMapping("/{id}/heatmap")
    public ResponseEntity<byte[]> heatmap(@PathVariable UUID id) {
        return image(studies.heatmap(users.require(), id));
    }

    @GetMapping("/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable UUID id) {
        return image(studies.image(users.require(), id));
    }

    private static ResponseEntity<byte[]> image(StudyService.ImageBytes img) {
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(img.contentType()))
                .cacheControl(CacheControl.noStore())    // patient imagery must not sit in shared caches
                .body(img.data());
    }
}
