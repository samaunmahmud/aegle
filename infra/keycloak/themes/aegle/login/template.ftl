<#--
  Aegle layout for every Keycloak login page: the imaging showcase on the left, the form on
  the right. Same macro and sections as Keycloak's base template.ftl, so any login page
  (sign-in, errors, password update, logout confirmation) renders inside it.
  Artwork: resources/img/art-*.svg, generated from the app's MedicalArt component
  (frontend/scripts/render-art.tsx).
-->
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="robots" content="noindex, nofollow">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Sign in · Aegle Clinical Imaging</title>
    <link rel="icon" href="${url.resourcesPath}/img/logo.svg" type="image/svg+xml" />
    <#if properties.styles?has_content>
        <#list properties.styles?split(' ') as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet" />
        </#list>
    </#if>
    <#if scripts??>
        <#list scripts as script>
            <script src="${script}" type="text/javascript"></script>
        </#list>
    </#if>
    <script type="module">
        import { checkCookiesAndSetTimer } from "${url.resourcesPath}/js/authChecker.js";
        checkCookiesAndSetTimer("${url.ssoLoginInOtherTabsUrl?no_esc}");
    </script>
</head>

<body class="aegle-login ${bodyClass}">
<main class="split">
    <section class="showcase" aria-label="About Aegle">
        <div class="brand">
            <img src="${url.resourcesPath}/img/logo.svg" alt="" width="40" height="40" />
            <div>
                <div class="brand-name">Aegle</div>
                <div class="brand-sub">Clinical Imaging</div>
            </div>
        </div>

        <div class="pitch">
            <h2>AI triage for every image that reaches the department.</h2>
            <p>Seven specialties, one reporting worklist. Models flag what looks urgent; a clinician reviews and signs every finding.</p>
        </div>

        <div class="mosaic" aria-hidden="true">
            <figure class="tile tile-wide"><img src="${url.resourcesPath}/img/art-radiology.svg" alt="" /><figcaption>Radiology <span>Chest X-ray</span></figcaption></figure>
            <figure class="tile"><img src="${url.resourcesPath}/img/art-neurology.svg" alt="" /><figcaption>Neurology <span>Brain MRI</span></figcaption></figure>
            <figure class="tile"><img src="${url.resourcesPath}/img/art-ophthalmology.svg" alt="" /><figcaption>Ophthalmology <span>Retina</span></figcaption></figure>
            <figure class="tile"><img src="${url.resourcesPath}/img/art-pathology.svg" alt="" /><figcaption>Pathology <span>H&amp;E</span></figcaption></figure>
            <figure class="tile"><img src="${url.resourcesPath}/img/art-dermatology.svg" alt="" /><figcaption>Dermatology <span>Dermoscopy</span></figcaption></figure>
            <figure class="tile tile-wide"><img src="${url.resourcesPath}/img/art-cardiology.svg" alt="" /><figcaption>Cardiology <span>12-lead ECG</span></figcaption></figure>
            <figure class="tile"><img src="${url.resourcesPath}/img/art-gastroenterology.svg" alt="" /><figcaption>Gastroenterology <span>Colonoscopy</span></figcaption></figure>
        </div>

        <ul class="assurances">
            <li>Encrypted end to end (TLS, mutual TLS for DICOM)</li>
            <li>Tamper-evident audit of every access</li>
            <li>Each AI model approved per organisation</li>
        </ul>
    </section>

    <section class="signin">
        <svg class="signin-pulse" viewBox="0 0 600 120" preserveAspectRatio="none" aria-hidden="true">
            <path d="M0 60h28l14-30 22 66 18-54 12 18h412l14-30 22 66 18-54 12 18h28" />
        </svg>
        <header class="signin-top">
            <div class="clinic">
                <svg class="clinic-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 21V8l8-5 8 5v13M9 21v-5h6v5M12 7v5M9.5 9.5h5" /></svg>
                <div>
                    <div class="clinic-name">Aegle Demo Clinic</div>
                    <div class="clinic-sub">Imaging &amp; Diagnostics</div>
                </div>
            </div>
            <div class="clock" aria-hidden="true"><span id="clock-day"></span><strong id="clock-time"></strong></div>
        </header>

        <div class="card">
            <div class="card-org">
                <span class="org-dot"></span> Secure clinical sign-in
            </div>

            <#if !(auth?has_content && auth.showUsername() && !auth.showResetCredentials())>
                <h1 id="kc-page-title"><#nested "header"></h1>
            <#else>
                <#nested "show-username">
                <div class="attempted">
                    <span>${auth.attemptedUsername}</span>
                    <a id="reset-login" href="${url.loginRestartFlowUrl}">Not you?</a>
                </div>
            </#if>

            <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="alert alert-${message.type}" role="alert">${kcSanitize(message.summary)?no_esc}</div>
            </#if>

            <#nested "form">

            <#if auth?has_content && auth.showTryAnotherWayLink()>
                <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post">
                    <input type="hidden" name="tryAnotherWay" value="on"/>
                    <button type="submit" class="link">${msg("doTryAnotherWay")}</button>
                </form>
            </#if>

            <#nested "socialProviders">

            <#if displayInfo>
                <div id="kc-info" class="info"><#nested "info"></div>
            </#if>

            <div class="notice">
                <strong>Authorised users only.</strong>
                Access to patient information is monitored and recorded in a tamper-evident audit log.
            </div>
            <div class="research">Research prototype · not a medical device · not for clinical use</div>
        </div>
        <div class="roles" aria-label="Who signs in here">
            <span class="roles-label">One sign-in, the right view for each role</span>
            <ul>
                <li><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>Radiologists</li>
                <li><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3v6a4 4 0 0 0 8 0V3M10 13v2a5 5 0 0 0 10 0v-2"/><circle cx="20" cy="11" r="2"/></svg>Physicians</li>
                <li><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/></svg>Auditors</li>
                <li><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/></svg>Admins</li>
            </ul>
        </div>

        <dl class="facts">
            <div><dt>7</dt><dd>departments</dd></div>
            <div><dt>11</dt><dd>AI models</dd></div>
            <div><dt>100%</dt><dd>of findings signed by a clinician</dd></div>
        </dl>

        <footer class="signin-foot">
            <p class="help">Trouble signing in? Contact your system administrator.</p>
            <p class="fine">Aegle · research prototype · &copy; 2026</p>
        </footer>
        <script>
            (function () {
                var day = document.getElementById("clock-day"), time = document.getElementById("clock-time");
                function tick() {
                    var d = new Date();
                    day.textContent = d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
                    time.textContent = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
                }
                tick(); setInterval(tick, 15000);
            })();
        </script>
    </section>
</main>
</body>
</html>
</#macro>
