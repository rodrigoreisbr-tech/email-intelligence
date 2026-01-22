import argparse
import datetime as dt
import os
import textwrap
import urllib.parse
from typing import Iterable, Optional

import msal
import requests
from dotenv import load_dotenv
from requests import HTTPError

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
OPENAI_BASE_URL = "https://api.openai.com/v1"
PROXY_DISABLE_VALUES = {"1", "true", "yes", "on"}


def load_settings() -> dict:
    load_dotenv()
    required = [
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "OPENAI_API_KEY",
        "TARGET_USER_EMAIL",
        "TEAMS_CHAT_ID",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise SystemExit(f"Missing environment variables: {', '.join(missing)}")

    return {
        "tenant_id": os.getenv("AZURE_TENANT_ID"),
        "client_id": os.getenv("AZURE_CLIENT_ID"),
        "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "target_user_email": os.getenv("TARGET_USER_EMAIL"),
        "bot_user_email": os.getenv("BOT_USER_EMAIL"),
        "teams_chat_id": os.getenv("TEAMS_CHAT_ID"),
        "default_summary_language": os.getenv("DEFAULT_SUMMARY_LANGUAGE", "pt-BR"),
        "proxy_url": os.getenv("PROXY_URL"),
        "disable_proxy": os.getenv("DISABLE_PROXY", "").strip().lower() in PROXY_DISABLE_VALUES,
        "delegated_client_id": os.getenv("DELEGATED_CLIENT_ID"),
        "delegated_scopes": os.getenv(
            "DELEGATED_SCOPES",
            "User.Read OnlineMeetings.Read OnlineMeetingTranscript.Read",
        ).split(),
    }


def build_http_session(proxy_url: Optional[str], disable_proxy: bool) -> requests.Session:
    session = requests.Session()
    if disable_proxy:
        session.trust_env = False
    elif proxy_url:
        session.proxies = {"http": proxy_url, "https": proxy_url}
    return session


def build_logger(log_path: Optional[str]):
    if not log_path:
        return None

    def _log(message: str) -> None:
        log_dir = os.path.dirname(log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    return _log


def build_msal_proxies(proxy_url: Optional[str], disable_proxy: bool) -> Optional[dict]:
    if disable_proxy:
        return {}
    if proxy_url:
        return {"http": proxy_url, "https": proxy_url}
    return None


class GraphClient:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        session: requests.Session,
        proxies: Optional[dict],
        debug: bool = False,
        log_path: Optional[str] = None,
    ):
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._session = session
        self._debug = debug
        self._log_to_file = build_logger(log_path)
        self._app = msal.ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=authority,
            http_client=session,
            proxies=proxies,
        )
        self._delegated_app: Optional[msal.PublicClientApplication] = None
        self._delegated_token: Optional[str] = None

    def _log(self, message: str) -> None:
        if self._debug:
            print(message)
        if self._log_to_file:
            self._log_to_file(message)

    def _get_access_token(self) -> str:
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            raise RuntimeError(f"Could not obtain access token: {result}")
        return result["access_token"]

    def _get_delegated_token(self, client_id: str, tenant_id: str, scopes: list[str]) -> str:
        if self._delegated_token:
            return self._delegated_token
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._delegated_app = msal.PublicClientApplication(
            client_id=client_id,
            authority=authority,
        )
        flow = self._delegated_app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise RuntimeError(f"Falha ao iniciar device flow: {flow}")
        print("Faca login no browser:", flush=True)
        message = flow.get("message")
        print(message, flush=True)
        self._log("[DELEGATED] Device flow iniciado.")
        if message:
            self._log(f"[DELEGATED] {message}")
        result = self._delegated_app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Falha no device flow: {result}")
        self._delegated_token = result["access_token"]
        self._log("[DELEGATED] Token delegado obtido.")
        return self._delegated_token

    def _ensure_delegated_token(self, delegated: dict) -> str:
        token = delegated.get("token")
        if token:
            return token
        token = self._get_delegated_token(
            delegated["client_id"],
            delegated["tenant_id"],
            delegated["scopes"],
        )
        delegated["token"] = token
        return token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        headers.setdefault("Prefer", 'outlook.timezone="UTC"')
        self._log(f"[HTTP] {method} {GRAPH_BASE_URL}{path}")
        response = self._session.request(
            method,
            f"{GRAPH_BASE_URL}{path}",
            headers=headers,
            timeout=30,
            **kwargs,
        )
        request_id = response.headers.get("request-id")
        self._log(f"[HTTP] status={response.status_code} request-id={request_id}")
        if response.status_code >= 400:
            self._log(f"[HTTP] response={response.text}")
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    def _request_with_base(self, method: str, base_url: str, path: str, **kwargs) -> dict:
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        self._log(f"[HTTP] {method} {base_url}{path}")
        response = self._session.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            timeout=30,
            **kwargs,
        )
        request_id = response.headers.get("request-id")
        self._log(f"[HTTP] status={response.status_code} request-id={request_id}")
        if response.status_code >= 400:
            self._log(f"[HTTP] response={response.text}")
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    def _request_with_delegated(
        self,
        method: str,
        base_url: str,
        path: str,
        delegated_token: str,
        **kwargs,
    ) -> dict:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {delegated_token}"
        headers["Content-Type"] = "application/json"
        self._log(f"[HTTP-DELEGATED] {method} {base_url}{path}")
        response = self._session.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            timeout=30,
            **kwargs,
        )
        request_id = response.headers.get("request-id")
        self._log(f"[HTTP-DELEGATED] status={response.status_code} request-id={request_id}")
        if response.status_code >= 400:
            self._log(f"[HTTP-DELEGATED] response={response.text}")
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    def get_user(self, user_email: str) -> dict:
        return self._request("GET", f"/users/{user_email}")

    def list_online_meetings(
        self,
        user_email: str,
        start: dt.datetime,
        end: dt.datetime,
        delegated: Optional[dict] = None,
        verbose: bool = False,
    ) -> list[dict]:
        filter_query = (
            f"startDateTime ge {start.isoformat()}Z and endDateTime le {end.isoformat()}Z"
        )
        meetings = []
        url = f"/users/{user_email}/onlineMeetings?$filter={filter_query}"
        while url:
            try:
                data = self._request("GET", url)
            except HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    if verbose:
                        print("Endpoint /onlineMeetings retornou 404. Usando calendarView.")
                    return self.list_online_meetings_from_calendar(
                        user_email,
                        start,
                        end,
                        delegated=delegated,
                    )
                raise
            meetings.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            if url and url.startswith(GRAPH_BASE_URL):
                url = url.replace(GRAPH_BASE_URL, "")
        if verbose:
            print(f"Reuniões retornadas por /onlineMeetings: {len(meetings)}")
        if not meetings:
            print(
                "Nenhuma reunião retornada por /onlineMeetings. "
                "Tentando via calendarView (inclui reuniões onde o usuário é participante)."
            )
            return self.list_online_meetings_from_calendar(
                user_email,
                start,
                end,
                delegated=delegated,
                verbose=verbose,
            )
        return meetings

    def list_calendar_events(
        self,
        user_email: str,
        start: dt.datetime,
        end: dt.datetime,
        verbose: bool = False,
    ) -> list[dict]:
        url = (
            f"/users/{user_email}/calendarView?"
            f"startDateTime={start.isoformat()}Z&endDateTime={end.isoformat()}Z"
            "&$select=id,iCalUId,subject,start,end,onlineMeeting,onlineMeetingUrl,isOnlineMeeting,onlineMeetingProvider,organizer"
        )
        events = []
        while url:
            try:
                data = self._request("GET", url)
            except HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 403:
                    raise RuntimeError(
                        "Acesso negado ao calendário. "
                        "Conceda a permissão Calendars.Read (Application) "
                        "e dê admin consent ao tenant, depois tente novamente."
                    ) from exc
                raise
            events.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
            if url and url.startswith(GRAPH_BASE_URL):
                url = url.replace(GRAPH_BASE_URL, "")
        if verbose:
            print(f"Eventos de calendário encontrados: {len(events)}")
        return events

    def get_calendar_event(self, user_email: str, event_id: str) -> dict:
        url = (
            f"/users/{user_email}/events/{event_id}?"
            "$select=subject,start,end,onlineMeeting,onlineMeetingUrl"
        )
        return self._request("GET", url)

    def get_online_meeting_by_join_url(self, user_email: str, join_url: str) -> dict:
        payload = {"joinWebUrl": join_url}
        try:
            return self._request(
                "POST",
                "/communications/onlineMeetings/getByJoinWebUrl",
                json=payload,
            )
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return self._request(
                    "POST",
                    f"/users/{user_email}/onlineMeetings/getByJoinWebUrl",
                    json=payload,
                )
            raise

    def get_online_meeting_by_join_url_variants(
        self,
        user_email: str,
        join_url: str,
        verbose: bool = False,
        delegated: Optional[dict] = None,
    ) -> dict:
        attempts = []
        variants = [join_url]
        decoded = urllib.parse.unquote(join_url)
        if decoded != join_url:
            variants.append(decoded)
        bases = [
            (GRAPH_BASE_URL, "/communications/onlineMeetings/getByJoinWebUrl"),
            (GRAPH_BASE_URL, f"/users/{user_email}/onlineMeetings/getByJoinWebUrl"),
            ("https://graph.microsoft.com/beta", "/communications/onlineMeetings/getByJoinWebUrl"),
            ("https://graph.microsoft.com/beta", f"/users/{user_email}/onlineMeetings/getByJoinWebUrl"),
        ]
        last_exc = None
        for variant in variants:
            payload = {"joinWebUrl": variant}
            for base_url, path in bases:
                try:
                    return self._request_with_base("POST", base_url, path, json=payload)
                except HTTPError as exc:
                    last_exc = exc
                    status = exc.response.status_code if exc.response is not None else "desconhecido"
                    request_id = (
                        exc.response.headers.get("request-id")
                        if exc.response is not None
                        else None
                    )
                    attempts.append((base_url, path, status, request_id))
        # Fallback: filter by JoinWebUrl (v1.0 + beta)
        for variant in variants:
            filter_expr = f"JoinWebUrl eq '{variant}'"
            filter_enc = urllib.parse.quote(filter_expr, safe="=' ")
            for base_url in (GRAPH_BASE_URL, "https://graph.microsoft.com/beta"):
                path = f"/users/{user_email}/onlineMeetings?$filter={filter_enc}"
                try:
                    data = self._request_with_base("GET", base_url, path)
                    meetings = data.get("value", [])
                    if meetings:
                        return meetings[0]
                except HTTPError as exc:
                    last_exc = exc
                    status = exc.response.status_code if exc.response is not None else "desconhecido"
                    request_id = (
                        exc.response.headers.get("request-id")
                        if exc.response is not None
                        else None
                    )
                    attempts.append((base_url, path, status, request_id))
        if delegated:
            token = self._ensure_delegated_token(delegated)
            for variant in variants:
                payload = {"joinWebUrl": variant}
                for base_url in (GRAPH_BASE_URL, "https://graph.microsoft.com/beta"):
                    path = "/me/onlineMeetings/getByJoinWebUrl"
                    try:
                        return self._request_with_delegated(
                            "POST",
                            base_url,
                            path,
                            token,
                            json=payload,
                        )
                    except HTTPError as exc:
                        last_exc = exc
                        status = exc.response.status_code if exc.response is not None else "desconhecido"
                        request_id = (
                            exc.response.headers.get("request-id")
                            if exc.response is not None
                            else None
                        )
                        attempts.append((base_url, path, status, request_id))
                filter_expr = f"JoinWebUrl eq '{variant}'"
                filter_enc = urllib.parse.quote(filter_expr, safe="=' ")
                for base_url in (GRAPH_BASE_URL, "https://graph.microsoft.com/beta"):
                    path = f"/me/onlineMeetings?$filter={filter_enc}"
                    try:
                        data = self._request_with_delegated("GET", base_url, path, token)
                        meetings = data.get("value", [])
                        if meetings:
                            return meetings[0]
                    except HTTPError as exc:
                        last_exc = exc
                        status = exc.response.status_code if exc.response is not None else "desconhecido"
                        request_id = (
                            exc.response.headers.get("request-id")
                            if exc.response is not None
                            else None
                        )
                        attempts.append((base_url, path, status, request_id))
        if verbose and attempts:
            print("Tentativas de getByJoinWebUrl:")
            for base_url, path, status, request_id in attempts:
                rid = f", request-id={request_id}" if request_id else ""
                print(f"- {base_url}{path}: {status}{rid}")
        if last_exc:
            raise last_exc
        raise RuntimeError("Não foi possível resolver onlineMeeting via joinUrl.")

    def probe_online_meeting_by_join_url(self, user_email: str, join_url: str) -> dict:
        payload = {"joinWebUrl": join_url}
        result = {"communications": None, "user": None}
        try:
            self._request(
                "POST",
                "/communications/onlineMeetings/getByJoinWebUrl",
                json=payload,
            )
            result["communications"] = "ok"
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "desconhecido"
            result["communications"] = str(status)
        try:
            self._request(
                "POST",
                f"/users/{user_email}/onlineMeetings/getByJoinWebUrl",
                json=payload,
            )
            result["user"] = "ok"
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "desconhecido"
            result["user"] = str(status)
        return result

    def list_online_meetings_from_calendar(
        self,
        user_email: str,
        start: dt.datetime,
        end: dt.datetime,
        delegated: Optional[dict] = None,
        verbose: bool = False,
    ) -> list[dict]:
        meetings = []
        join_url_events = 0
        unresolved_by_join_url = 0
        for event in self.list_calendar_events(user_email, start, end, verbose=verbose):
            online_meeting = event.get("onlineMeeting") or {}
            join_url = online_meeting.get("joinUrl") or event.get("onlineMeetingUrl")
            provider = event.get("onlineMeetingProvider")
            if not join_url:
                event_id = event.get("id")
                if event_id:
                    event_details = self.get_calendar_event(user_email, event_id)
                    online_meeting = event_details.get("onlineMeeting") or {}
                    join_url = (
                        online_meeting.get("joinUrl")
                        or event_details.get("onlineMeetingUrl")
                    )
                    provider = event_details.get("onlineMeetingProvider") or provider
            if not join_url:
                if verbose:
                    subject = event.get("subject") or "Sem assunto"
                    print(f"Evento sem joinUrl, pulando: {subject}")
                continue
            join_url_events += 1
            if provider and provider.lower() != "teamsforbusiness":
                unresolved_by_join_url += 1
                if verbose:
                    subject = event.get("subject") or "Sem assunto"
                    print(
                        "Reunião não é Teams (provider={provider}), pulando: {subject}".format(
                            provider=provider, subject=subject
                        )
                    )
                continue
            try:
                meeting = self.get_online_meeting_by_join_url_variants(
                    user_email,
                    join_url,
                    verbose=verbose,
                    delegated=delegated,
                )
            except HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    unresolved_by_join_url += 1
                    if verbose:
                        subject = event.get("subject") or "Sem assunto"
                        print(
                            "Endpoint getByJoinWebUrl retornou 404. "
                            f"Não foi possível resolver a reunião: {subject}"
                        )
                    continue
                raise
            if not meeting:
                if verbose:
                    subject = event.get("subject") or "Sem assunto"
                    print(f"Falha ao resolver onlineMeeting via joinUrl: {subject}")
                continue
            meeting["subject"] = event.get("subject") or meeting.get("subject")
            start_obj = event.get("start") or {}
            end_obj = event.get("end") or {}
            meeting["startDateTime"] = start_obj.get("dateTime", meeting.get("startDateTime"))
            meeting["endDateTime"] = end_obj.get("dateTime", meeting.get("endDateTime"))
            meetings.append(meeting)
        if verbose:
            print(f"Reuniões encontradas via calendarView: {len(meetings)}")
        if not meetings and join_url_events > 0 and unresolved_by_join_url == join_url_events:
            print(
                "Encontramos eventos com joinUrl no calendário, mas não foi possível "
                "resolver o onlineMeeting via getByJoinWebUrl. "
                "Verifique permissões OnlineMeetings.Read.All e a application access policy."
            )
        return meetings

    def list_transcripts(
        self,
        user_email: str,
        meeting_id: str,
        delegated: Optional[dict] = None,
    ) -> list[dict]:
        try:
            data = self._request(
                "GET",
                f"/users/{user_email}/onlineMeetings/{meeting_id}/transcripts",
            )
            return data.get("value", [])
        except HTTPError:
            if not delegated:
                raise
        token = self._ensure_delegated_token(delegated)
        data = self._request_with_delegated(
            "GET",
            GRAPH_BASE_URL,
            f"/me/onlineMeetings/{meeting_id}/transcripts",
            token,
        )
        return data.get("value", [])

    def get_transcript_content(
        self,
        user_email: str,
        meeting_id: str,
        transcript_id: str,
        delegated: Optional[dict] = None,
    ) -> str:
        token = self._get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = self._session.get(
            f"{GRAPH_BASE_URL}/users/{user_email}/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content?$format=text/vtt",
            headers=headers,
            timeout=30,
        )
        if response.status_code == 200:
            return response.text
        if not delegated:
            response.raise_for_status()
        token = self._ensure_delegated_token(delegated)
        response = self._session.get(
            f"{GRAPH_BASE_URL}/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content?$format=text/vtt",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def send_chat_message(self, chat_id: str, message: str) -> None:
        payload = {
            "body": {
                "contentType": "html",
                "content": message,
            }
        }
        self._request("POST", f"/chats/{chat_id}/messages", json=payload)


def vtt_to_text(vtt: str) -> str:
    lines = []
    for line in vtt.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("WEBVTT"):
            continue
        if "-->" in stripped:
            continue
        lines.append(stripped)
    return " ".join(lines)


def summarize_transcript(
    session: requests.Session,
    openai_api_key: str,
    model: str,
    language: str,
    transcript: str,
) -> str:
    prompt = textwrap.dedent(
        f"""
        Você é um assistente que resume transcrições de reuniões do Teams.
        Gere um resumo em {language} com:
        - Principais tópicos
        - Decisões
        - Próximas ações
        """
    ).strip()

    response = session.post(
        f"{OPENAI_BASE_URL}/responses",
        headers={"Authorization": f"Bearer {openai_api_key}"},
        json={
            "model": model,
            "input": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    output_texts = [
        item.get("content", [{}])[0].get("text", "")
        for item in data.get("output", [])
        if item.get("type") == "message"
    ]
    summary = "\n".join(text for text in output_texts if text)
    if not summary:
        raise RuntimeError("OpenAI response did not return summary text.")
    return summary


def format_summary(meeting: dict, summary: str) -> str:
    title = meeting.get("subject") or "Reunião sem título"
    start = meeting.get("startDateTime")
    end = meeting.get("endDateTime")
    return textwrap.dedent(
        f"""
        <strong>Resumo da reunião</strong><br/>
        <strong>Título:</strong> {title}<br/>
        <strong>Início:</strong> {start}<br/>
        <strong>Fim:</strong> {end}<br/><br/>
        <pre>{summary}</pre>
        """
    ).strip()


def parse_iso_datetime(value: str) -> dt.datetime:
    sanitized = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(sanitized)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)


def get_time_window(
    since_days: int,
    start_iso: Optional[str],
    end_iso: Optional[str],
) -> tuple[dt.datetime, dt.datetime]:
    if start_iso and end_iso:
        return parse_iso_datetime(start_iso), parse_iso_datetime(end_iso)
    now = dt.datetime.utcnow()
    start = now - dt.timedelta(days=since_days)
    return start, now


def iter_transcripts(
    graph: GraphClient,
    user_email: str,
    since_days: int,
    start_iso: Optional[str],
    end_iso: Optional[str],
    calendar_only: bool,
    delegated: Optional[dict] = None,
    verbose: bool = False,
) -> Iterable[tuple[dict, str]]:
    start, end = get_time_window(since_days, start_iso, end_iso)
    if verbose:
        print(f"Buscando reuniões de {user_email} entre {start.isoformat()}Z e {end.isoformat()}Z")
    if calendar_only:
        if verbose:
            print("Usando apenas calendarView para buscar reuniões.")
        meetings = graph.list_online_meetings_from_calendar(
            user_email,
            start,
            end,
            delegated=delegated,
            verbose=verbose,
        )
    else:
        meetings = graph.list_online_meetings(
            user_email,
            start,
            end,
            delegated=delegated,
            verbose=verbose,
        )
    if not meetings:
        print("Nenhuma reunião encontrada no intervalo informado.")
    for meeting in meetings:
        meeting_id = meeting.get("id")
        if not meeting_id:
            continue
        if verbose:
            subject = meeting.get("subject") or "Sem assunto"
            print(f"Verificando transcrições da reunião: {subject} ({meeting_id})")
        transcripts = graph.list_transcripts(user_email, meeting_id, delegated=delegated)
        if verbose:
            print(f"Transcrições encontradas: {len(transcripts)}")
        if not transcripts:
            print("Reunião sem transcrição disponível, pulando.")
            continue
        transcript_id = transcripts[0].get("id")
        if not transcript_id:
            continue
        vtt_content = graph.get_transcript_content(
            user_email,
            meeting_id,
            transcript_id,
            delegated=delegated,
        )
        yield meeting, vtt_to_text(vtt_content)


def check_access(
    graph: GraphClient,
    user_email: str,
    since_days: int,
    start_iso: Optional[str],
    end_iso: Optional[str],
    verbose: bool = False,
) -> None:
    start, end = get_time_window(since_days, start_iso, end_iso)
    print(f"Checando acesso para {user_email} entre {start.isoformat()}Z e {end.isoformat()}Z")

    try:
        graph.get_user(user_email)
        print("[OK] Acesso a /users OK")
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        print(f"[ERRO] Falha em /users: {status}")
        return

    try:
        graph.list_online_meetings(user_email, start, end, verbose=True)
        print("[OK] Acesso a /onlineMeetings OK")
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        print(f"[ERRO] Falha em /onlineMeetings: {status}")

    try:
        graph.list_calendar_events(user_email, start, end, verbose=True)
        print("[OK] Acesso a /calendarView OK")
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        print(f"[ERRO] Falha em /calendarView: {status}")

    events: list[dict] = []
    try:
        events = graph.list_calendar_events(user_email, start, end, verbose=False)
        join_url = None
        for event in events:
            online_meeting = event.get("onlineMeeting") or {}
            join_url = online_meeting.get("joinUrl") or event.get("onlineMeetingUrl")
            if join_url:
                break
        if join_url:
            probe = graph.probe_online_meeting_by_join_url(user_email, join_url)
            communications_status = probe.get("communications")
            user_status = probe.get("user")
            if communications_status == "ok":
                print("[OK] Acesso a /communications/onlineMeetings/getByJoinWebUrl OK")
            else:
                print(
                    "[ERRO] Falha em /communications/onlineMeetings/getByJoinWebUrl: "
                    f"{communications_status}"
                )
            if user_status == "ok":
                print("[OK] Acesso a /users/{id}/onlineMeetings/getByJoinWebUrl OK")
            else:
                print(
                    "[ERRO] Falha em /users/{id}/onlineMeetings/getByJoinWebUrl: "
                    f"{user_status}"
                )
        else:
            print("[AVISO] Nenhum joinUrl encontrado nos eventos para testar getByJoinWebUrl.")
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        print(f"[ERRO] Falha ao preparar teste de getByJoinWebUrl: {status}")

    if verbose and events:
        print("Detalhes dos eventos retornados:")
        for event in events:
            subject = event.get("subject") or "Sem assunto"
            event_id = event.get("id") or "sem-id"
            organizer = (event.get("organizer") or {}).get("emailAddress", {}).get("address")
            is_online = event.get("isOnlineMeeting")
            provider = event.get("onlineMeetingProvider")
            online_meeting = event.get("onlineMeeting") or {}
            join_url = online_meeting.get("joinUrl") or event.get("onlineMeetingUrl")
            print(
                f"- {subject} | id={event_id} | organizer={organizer} | "
                f"isOnlineMeeting={is_online} | provider={provider} | joinUrl={'sim' if join_url else 'não'}"
            )


def run(
    since_days: int,
    start_iso: Optional[str],
    end_iso: Optional[str],
    dry_run: bool,
    limit: Optional[int],
    calendar_only: bool,
    verbose: bool,
    check_only: bool,
) -> None:
    settings = load_settings()
    http_session = build_http_session(settings["proxy_url"], settings["disable_proxy"])
    msal_proxies = build_msal_proxies(settings["proxy_url"], settings["disable_proxy"])
    log_path = os.getenv("LOG_PATH")
    graph = GraphClient(
        settings["tenant_id"],
        settings["client_id"],
        settings["client_secret"],
        http_session,
        msal_proxies,
        debug=verbose,
        log_path=log_path,
    )

    delegated = None
    if settings["delegated_client_id"]:
        delegated = {
            "client_id": settings["delegated_client_id"],
            "tenant_id": settings["tenant_id"],
            "scopes": settings["delegated_scopes"],
            "token": None,
        }

    if check_only:
        check_access(
            graph,
            settings["target_user_email"],
            since_days,
            start_iso,
            end_iso,
            verbose=verbose,
        )
        return

    processed = 0
    for meeting, transcript in iter_transcripts(
        graph,
        settings["target_user_email"],
        since_days,
        start_iso,
        end_iso,
        calendar_only,
        delegated=delegated,
        verbose=verbose,
    ):
        summary = summarize_transcript(
            http_session,
            settings["openai_api_key"],
            settings["openai_model"],
            settings["default_summary_language"],
            transcript,
        )
        formatted = format_summary(meeting, summary)
        if dry_run:
            print("-" * 80)
            print(formatted)
        else:
            graph.send_chat_message(settings["teams_chat_id"], formatted)
        processed += 1
        if limit and processed >= limit:
            break
    if processed == 0:
        print(
            "Nenhuma transcrição processada. Verifique se há reuniões com transcrição no período "
            "e se o e-mail do usuário está correto."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resume transcrições do Teams e envia resumo para chat.",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=3,
        help="Quantidade de dias para buscar reuniões.",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Início do intervalo em ISO-8601 (ex.: 2026-01-21T00:00:00Z).",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Fim do intervalo em ISO-8601 (ex.: 2026-01-21T23:59:59Z).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não envia para o Teams, apenas imprime o resumo.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita a quantidade de reuniões processadas.",
    )
    parser.add_argument(
        "--calendar-only",
        action="store_true",
        help="Usa apenas calendarView para localizar reuniões (ignora /onlineMeetings).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Exibe mensagens detalhadas de diagnóstico.",
    )
    parser.add_argument(
        "--check-access",
        action="store_true",
        help="Verifica acesso às APIs do Graph e imprime o status.",
    )
    parser.add_argument(
        "--log-path",
        type=str,
        default=None,
        help="Caminho opcional para salvar logs detalhados.",
    )
    args = parser.parse_args()
    if args.log_path:
        os.environ["LOG_PATH"] = args.log_path
    run(
        args.since_days,
        args.start,
        args.end,
        args.dry_run,
        args.limit,
        args.calendar_only,
        args.verbose,
        args.check_access,
    )
 
