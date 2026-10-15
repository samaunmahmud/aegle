<#-- Sign-in form. Field names and ids match Keycloak's base login.ftl (the login flow posts them). -->
<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=realm.password && realm.registrationAllowed && !registrationDisabled??; section>
    <#if section = "header">
        Sign in
    <#elseif section = "form">
        <p class="lead">Use your hospital account to open the reporting worklist.</p>
        <#if realm.password>
            <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post" novalidate>
                <#if !usernameHidden??>
                    <div class="field">
                        <label for="username"><#if !realm.loginWithEmailAllowed>Username<#elseif !realm.registrationEmailAsUsername>Username or email<#else>Email</#if></label>
                        <input tabindex="2" id="username" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="username" spellcheck="false"
                               aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                    </div>
                </#if>

                <div class="field">
                    <label for="password">Password</label>
                    <div class="password-wrap">
                        <input tabindex="3" id="password" name="password" type="password" autocomplete="current-password"
                               aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                        <button class="reveal" type="button" aria-label="Show password" aria-controls="password" data-password-toggle tabindex="4"
                                data-icon-show="eye" data-icon-hide="eye-off" data-label-show="Show password" data-label-hide="Hide password">
                            <i class="eye" aria-hidden="true"></i>
                        </button>
                    </div>
                </div>

                <#if messagesPerField.existsError('username','password')>
                    <div class="field-error" id="input-error" aria-live="polite">
                        ${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}
                    </div>
                </#if>

                <div class="options">
                    <#if realm.rememberMe && !usernameHidden??>
                        <label class="check">
                            <input tabindex="5" id="rememberMe" name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if>> Keep me signed in on this workstation
                        </label>
                    </#if>
                    <#if realm.resetPasswordAllowed>
                        <a tabindex="6" href="${url.loginResetCredentialsUrl}">Forgot password?</a>
                    </#if>
                </div>

                <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
                <button tabindex="7" class="primary" name="login" id="kc-login" type="submit">Sign in</button>
            </form>
        </#if>
        <script type="module" src="${url.resourcesPath}/js/passwordVisibility.js"></script>
    <#elseif section = "info">
        <#if realm.password && realm.registrationAllowed && !registrationDisabled??>
            <span>No account? <a tabindex="8" href="${url.registrationUrl}">Request access</a></span>
        </#if>
    <#elseif section = "socialProviders">
        <#if realm.password && social?? && social.providers?has_content>
            <div class="social">
                <div class="divider"><span>or</span></div>
                <#list social.providers as p>
                    <a id="social-${p.alias}" class="secondary-button" href="${p.loginUrl}">${p.displayName!}</a>
                </#list>
            </div>
        </#if>
    </#if>
</@layout.registrationLayout>
