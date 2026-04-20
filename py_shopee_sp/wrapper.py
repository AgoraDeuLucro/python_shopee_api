import requests
from time import sleep


class SPAPIError(Exception):
    """Exceção base para erros da Amazon SP-API."""
    def __init__(self, message, status_code=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RateLimitExceededError(SPAPIError):
    """Exceção para quando o rate limit é excedido e as tentativas de retry se esgotam."""
    pass


class auth():
    """Classe base com autenticação e controle de requisições para a Amazon SP-API.
    
    A SP-API utiliza o algoritmo de token bucket para rate limiting, com limites
    dinâmicos por operação e par vendedor/aplicação. Por isso, o controle de rate
    limit é feito de forma reativa: em caso de HTTP 429, a requisição é retentada
    com backoff exponencial (1s → 2s → 4s), conforme recomendação oficial da Amazon.
    
    Referência: https://developer-docs.amazon.com/sp-api/docs/usage-plans-and-rate-limits
    """

    _ENDPOINTS = {
        'na': 'https://sellingpartnerapi-na.amazon.com',  # América do Norte (US, CA, MX, BR)
        'eu': 'https://sellingpartnerapi-eu.amazon.com',  # Europa (UK, DE, FR, IT, ES, etc.)
        'fe': 'https://sellingpartnerapi-fe.amazon.com',  # Extremo Oriente (JP, AU, SG)
    }

    _MAX_RETRIES = 3

    def __init__(self, access_token="", region="na", print_error=True):
        """
        Args:
            access_token (str): Token de acesso para a SP-API (LWA access token).
            region (str): Região do endpoint ('na', 'eu', 'fe').
            print_error (bool): Se True, imprime detalhes de erros no console.
        """
        if region not in self._ENDPOINTS:
            raise ValueError(f"Região inválida. Escolha entre: {', '.join(self._ENDPOINTS.keys())}")

        self.access_token = access_token
        self.region = region
        self.endpoint = self._ENDPOINTS[region]
        self.print_error = print_error

    def request(self, method="GET", url="", headers=None, params=None, data=None):
        """Método unificado para requisições à SP-API com retry em 429.

        Em caso de HTTP 429 (rate limit), aguarda com backoff exponencial e retenta
        automaticamente até _MAX_RETRIES vezes antes de lançar RateLimitExceededError.

        Args:
            method (str): Método HTTP ('GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS').
            url (str): URL completa da requisição.
            headers (dict): Headers adicionais (mesclados com os padrão).
            params (dict): Parâmetros de query string.
            data: Corpo da requisição (passar json.dumps(dict) para enviar JSON).

        Returns:
            requests.Response: Objeto de resposta em caso de sucesso (200 ou 201).
            None: Em caso de 403 ou 404.
        """
        req_params = params if params is not None else {}
        req_headers = headers if headers is not None else {}
        req_data = data if data is not None else {}

        if self.access_token:
            req_headers["x-amz-access-token"] = self.access_token

        req_headers.setdefault("Content-Type", "application/json")
        req_headers.setdefault("Accept", "application/json")

        retries = 0
        delay = 1

        while True:
            match method:
                case "GET":
                    response = requests.get(url=url, params=req_params, headers=req_headers, data=req_data)
                case "PUT":
                    response = requests.put(url=url, params=req_params, headers=req_headers, data=req_data)
                case "POST":
                    response = requests.post(url=url, params=req_params, headers=req_headers, data=req_data)
                case "DELETE":
                    response = requests.delete(url=url, params=req_params, headers=req_headers, data=req_data)
                case "HEAD":
                    response = requests.head(url=url, params=req_params, headers=req_headers, data=req_data)
                case "OPTIONS":
                    response = requests.options(url=url, params=req_params, headers=req_headers, data=req_data)

            if response.status_code in (200, 201):
                return response

            elif response.status_code == 429:
                retries += 1
                if retries > self._MAX_RETRIES:
                    raise RateLimitExceededError(
                        f"Rate limit excedido após {self._MAX_RETRIES} tentativas. Tente novamente mais tarde.",
                        status_code=429
                    )
                if self.print_error:
                    rate_limit = response.headers.get("x-amzn-RateLimit-Limit", "desconhecido")
                    print(
                        f"Rate limit atingido (x-amzn-RateLimit-Limit: {rate_limit}). "
                        f"Aguardando {delay}s antes de retentar "
                        f"(tentativa {retries}/{self._MAX_RETRIES})..."
                    )
                sleep(delay)
                delay *= 2

            else:
                if self.print_error:
                    try:
                        response_json = response.json()
                        errors = response_json.get('errors', [])
                        message = errors[0].get('message', '') if errors else response_json.get('message', '')
                        json_content = response_json
                    except Exception:
                        message = ""
                        json_content = response.text

                    print(f"""Erro no retorno da SP-API
Mensagem: {message}
URL: {url}
Método: {method}
Parâmetros: {req_params}
Headers: {req_headers}
Data: {req_data}
Resposta JSON: {json_content}""")

                if response.status_code in (403, 404):
                    return None
                else:
                    break


class invoices(auth):
    """Operações da API de Notas Fiscais (Invoices) da Amazon SP-API.

    Documentação: https://developer-docs.amazon.com/sp-api/docs/invoices-api
    """

    def get_invoices(self, marketplace_id, **kwargs):
        """Busca notas fiscais com base nos parâmetros informados.

        Args:
            marketplace_id (str): ID do Marketplace da Amazon.
                                  Ex: 'A2Q3Y263D00KWC' para o Brasil.
            **kwargs: Parâmetros de filtro adicionais:
                - dateStart (str): Data de início no formato ISO 8601 (YYYY-MM-DD).
                - dateEnd (str): Data de fim no formato ISO 8601 (YYYY-MM-DD).

        Returns:
            dict: Dados das notas fiscais ou dict vazio se falhou.
        """
        url = self.endpoint + "/tax/invoices/2024-06-19/invoices"

        params = {"marketplaceId": marketplace_id}
        params.update(kwargs)

        response = self.request("GET", url=url, params=params)

        if response:
            return response.json()
        return {}

    def get_invoice_document(self, document_id):
        """Recupera os detalhes de um documento de nota fiscal específico.

        Args:
            document_id (str): ID do documento da nota fiscal.

        Returns:
            dict: Dados do documento ou dict vazio se falhou.
        """
        url = self.endpoint + f"/tax/invoices/2024-06-19/documents/{document_id}"

        response = self.request("GET", url=url)

        if response:
            return response.json()
        return {}
