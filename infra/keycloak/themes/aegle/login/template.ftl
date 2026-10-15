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
        <p class="help">Trouble signing in? Contact your system administrator.</p>
    </section>
</main>
</body>
</html>
</#macro>
