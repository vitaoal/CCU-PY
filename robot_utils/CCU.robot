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

Aguardar Desbloqueio
    Wait Until Element Is Not Visible
    ...    xpath=//div[contains(@class,"ccuBloqueio")]
    ...    ${CONFIG["timeouts"]["visibilidade"]}

Buscar Painel Com Mes e Ano
    [Arguments]    ${mes_ano}

    Log To Console    STEP: Buscando mês
    
    ${painel_texto}=    Get Text
    ...    xpath=//strong[@id="ccuAnoMesAtual"]

    WHILE    True
        ${painel_texto}=    Get Text    xpath=//strong[@id="ccuAnoMesAtual"]
        Exit For Loop If    '${painel_texto}' == '${mes_ano}'

        Click Element    xpath=//button[@id="mesAnterior"]
        Aguardar Desbloqueio
    END

Salvar Dicionario Em CSV
    [Arguments]    &{HORAS_POR_DIA}

    Log To Console    STEP: Gerando CSV

    ${arquivo}=    Set Variable    ${CONFIG["arquivos"]["csv_horas"]}
    ${conteudo}=    Set Variable    dia, data_inicial, inicio_intercalo, fim_intercalo, data_final\n

    FOR    ${dia}    IN    @{HORAS_POR_DIA.keys()}
        ${dados}=    Get From Dictionary    ${HORAS_POR_DIA}    ${dia}
        ${inicio}=   Get From Dictionary    ${dados}    hora_inicio
        ${inicio_intercalo}=   Get From Dictionary    ${dados}    inicio_intercalo
        ${fim_intercalo}=      Get From Dictionary    ${dados}    fim_intercalo    
        ${fim}=      Get From Dictionary    ${dados}    hora_fim
        ${linha}=    Set Variable    ${dia},${inicio},${inicio_intercalo},${fim_intercalo},${fim}\n
        ${conteudo}=    Catenate    SEPARATOR=    ${conteudo}    ${linha}
    END

    Create File    ${arquivo}    ${conteudo}


Esperar Tela De Dias
    
    Wait Until Page Contains Element
    ...    xpath=//table[@id="ccuDias"]
    ...    ${CONFIG["timeouts"]["visibilidade"]}

    Aguardar Desbloqueio


Coletar Horas Por Dia
    
    Log To Console    STEP: Extraindo dados

    &{HORAS_POR_DIA}=    Create Dictionary

    ${total_dias}=    Get Element Count
    ...    xpath=//table[@id="ccuDias"]//span[contains(@class, "ccuDia")]

    FOR    ${i}    IN RANGE    ${total_dias}
        ${dia_texto}    ${dados_dia}=    Processar Dia Por Indice    ${i}
        Set To Dictionary    ${HORAS_POR_DIA}    ${dia_texto}=${dados_dia}
    END

    RETURN    ${HORAS_POR_DIA}


Processar Dia Por Indice
    [Arguments]    ${indice}

    Aguardar Desbloqueio

    ${dia}=    Get WebElement
    ...    xpath=(//table[@id="ccuDias"]//span[contains(@class, "ccuDia")])[${indice + 1}]

    ${dia_texto}=    Get Text    ${dia}

    Click Element
    ...    xpath=(//table[@id="ccuDias"]//span[contains(@class, "ccuDia")])[${indice + 1}]

    Aguardar Desbloqueio

    ${dados_dia}=    Coletar Horas Do Dia

    RETURN    ${dia_texto}    ${dados_dia}


Coletar Horas Do Dia

    ${horas_validas}=    Execute Javascript
    ...    const vals = [...document.querySelectorAll('#ccuLancamentos input.hora')]
    ...      .map(e => e.value)
    ...      .filter(v => v);
    ...    return vals;

    ${qtd_horas}=    Get Length    ${horas_validas}

    ${hora_inicio}=    Set Variable If
    ...    ${qtd_horas} > 0
    ...    ${horas_validas}[0]
    ...    ${EMPTY}

    ${hora_fim}=    Set Variable If
    ...    ${qtd_horas} > 1
    ...    ${horas_validas}[-1]
    ...    ${EMPTY}
    
    ${inicio_intercalo}=      Set Variable  ${EMPTY}
    ${fim_intercalo}=         Set Variable  ${EMPTY}
    
    IF    ${qtd_horas} == 4
        ${inicio_intercalo}=    Set Variable    ${horas_validas}[1]
        ${fim_intercalo}=       Set Variable    ${horas_validas}[-2]
    END

    &{dados_dia}=    Create Dictionary
    ...    hora_inicio=${hora_inicio}
    ...    inicio_intercalo=${inicio_intercalo}
    ...    fim_intercalo=${fim_intercalo}
    ...    hora_fim=${hora_fim}

    RETURN    ${dados_dia}

Logar
    Input Text      id=username    ${CONFIG["usuario"]}
    Input Password  id=password    ${CONFIG["senha"]}
    Click Button    id=kc-login

    Log To Console    STEP: Login concluído

*** Test Cases ***
Setup
    Set Environment Variable    PYTHONPATH    ${ROOT}

Teste Extrair Horas CCU
    
    ${CONFIG}=     Carregar Configuracoes
    Set Suite Variable    ${CONFIG}

    Abrir Navegador   ${CONFIG}    ${DEBUG}    URL=${CONFIG["url"]}
    
    Logar

    Esperar Tela De Dias

    Buscar Painel Com Mes e Ano    ${DATA_PARAM}
    
    &{HORAS_POR_DIA}=    Coletar Horas Por Dia
    Salvar Dicionario Em CSV    &{HORAS_POR_DIA}

    Log To Console    STEP: CSV criado com sucesso

    Close Browser
