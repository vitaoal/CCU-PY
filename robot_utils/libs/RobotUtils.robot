*** Settings ***

Library    SeleniumLibrary
Library    BuiltIn
Library    OperatingSystem
Library    Collections
Library    CryptoLibrary.py


*** Variables ***

${ROOT}    ${CURDIR}/../..
*** Keywords ***

Abrir Navegador
    [Arguments]    ${CONFIG}    ${DEBUG}    ${URL}

    Log To Console    STEP: Logando na intranet
    
    ${BROWSER}=    Set Variable    ${CONFIG["browser"]}
    
    # Configurações Específicas para Chrome
    IF    '${BROWSER}' == 'chrome'
        ${options}=    Evaluate
        ...    sys.modules['selenium.webdriver'].ChromeOptions()    sys

        IF    not ${DEBUG}
            Call Method    ${options}    add_argument    --headless=new
            Call Method    ${options}    add_argument    --disable-gpu
            Call Method    ${options}    add_argument    --disable-extensions
            Call Method    ${options}    add_argument    --disable-notifications
            Call Method    ${options}    add_argument    --disable-infobars
            Call Method    ${options}    add_argument    --disable-dev-shm-usage
        END

        Call Method    ${options}    add_argument    --window-size=1920,1080

    # Configurações Específicas para Firefox
    ELSE IF    '${BROWSER}' == 'firefox'
        ${options}=    Evaluate
        ...    sys.modules['selenium.webdriver'].FirefoxOptions()    sys

        IF    not ${DEBUG}
            Call Method    ${options}    add_argument    -headless
            Call Method    ${options}    set_preference    dom.webnotifications.enabled    False
            Call Method    ${options}    set_preference    media.autoplay.default    5
        END
        
        Set Environment Variable    GECKODRIVER_LOG    fatal
        Set Environment Variable    MOZ_LOG            fatal
        
    ELSE
        Fail    Navegador inválido: ${CONFIG["browser"]}
    END
    
    Open Browser
    ...    ${URL}
    ...    ${BROWSER}
    ...    options=${options}
    ...    service_log_path=${NONE}

Carregar Configuracoes
    ${json_text}=    Get File    ${ROOT}/configs/config.json
    ${config}=       Evaluate    json.loads($json_text)    json

    ${senha_plana}=  Decrypt    ${config["senha"]}
    ${senha_email_plana}=  Decrypt    ${config["email"]["senha_email"]}
    Set To Dictionary    ${config}    senha=${senha_plana}
    Set To Dictionary    ${config["email"]}    senha_email=${senha_email_plana}

    RETURN    ${config}

