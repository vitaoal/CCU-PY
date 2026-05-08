*** Settings ****
Library    SeleniumLibrary
Library    OperatingSystem
Library    Collections
Library    Dialogs
Library    libs/CryptoLibrary.py
Resource   libs/RobotUtils.robot

*** Variables ***

${CONFIG}    None
${DEBUG}    True
${ROOT}    ${CURDIR}/..

*** Keywords ***

Logar
    Input Text      id=rcmloginuser    ${CONFIG["email"]["usuario_email"]}
    Input Password  id=rcmloginpwd    ${CONFIG["email"]["senha_email"]}
    Click Button    id=rcmloginsubmit

    Log To Console    STEP: Login concluído

*** Test Cases ***
Teste Extrair Horas CCU
    
    ${CONFIG}=     Carregar Configuracoes
    Set Suite Variable    ${CONFIG}

    Abrir Navegador    ${CONFIG}    ${DEBUG}    URL=${CONFIG["email"]["url_email"]}
    
    Logar
    
    Sleep     0.5s

    Wait Until Element Is Visible    id=rcmbtn103    10s

    Click Element                   id=rcmbtn103



