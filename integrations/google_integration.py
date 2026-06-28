from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

_JARVIS_DIR = Path.home() / ".jarvis"
_TOKEN_PATH = _JARVIS_DIR / "google_credentials.json"
_SECRET_PATH = _JARVIS_DIR / "google_client_secret.json"

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

try:
    import google.auth.transport.requests
    import google.oauth2.credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    _GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    _GOOGLE_LIBS_AVAILABLE = False


def _load_credentials():
    if not _GOOGLE_LIBS_AVAILABLE:
        return None
    if not _TOKEN_PATH.exists():
        return None
    try:
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
            str(_TOKEN_PATH), _SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
            _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
            _TOKEN_PATH.write_text(creds.to_json())
        return creds if creds and creds.valid else None
    except Exception:
        return None


def _authorize_new() -> Optional[object]:
    if not _GOOGLE_LIBS_AVAILABLE or not _SECRET_PATH.exists():
        return None
    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(_SECRET_PATH), _SCOPES)
        creds = flow.run_local_server(port=0)
        _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        _TOKEN_PATH.write_text(creds.to_json())
        return creds
    except Exception:
        return None


def _get_creds():
    creds = _load_credentials()
    if creds is None:
        creds = _authorize_new()
    return creds


def _format_event_for_voice(event: dict) -> str:
    summary = event.get("summary", "Sem título")
    start = event.get("start", {})
    dt_str = start.get("dateTime") or start.get("date", "")
    if "T" in dt_str:
        try:
            dt = datetime.fromisoformat(dt_str)
            time_str = dt.strftime("%H:%M")
        except ValueError:
            time_str = dt_str
    else:
        time_str = "dia inteiro"
    return f"{summary} às {time_str}"


class GoogleIntegration:
    def is_available(self) -> bool:
        if not _GOOGLE_LIBS_AVAILABLE:
            return False
        return _TOKEN_PATH.exists() and _SECRET_PATH.exists()

    def _calendar_service(self):
        creds = _get_creds()
        if creds is None:
            return None
        try:
            return build("calendar", "v3", credentials=creds)
        except Exception:
            return None

    def _gmail_service(self):
        creds = _get_creds()
        if creds is None:
            return None
        try:
            return build("gmail", "v1", credentials=creds)
        except Exception:
            return None

    def get_today_events(self) -> str:
        if not self.is_available():
            return "Google Calendar não está disponível. Instale as dependências e configure as credenciais."
        service = self._calendar_service()
        if service is None:
            return "Não foi possível conectar ao Google Calendar."
        try:
            now = datetime.now(timezone.utc)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
            result = service.events().list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = result.get("items", [])
            if not events:
                return "Você não tem eventos hoje."
            lines = [_format_event_for_voice(e) for e in events]
            return f"Hoje você tem {len(events)} evento(s): " + "; ".join(lines) + "."
        except Exception as exc:
            return f"Erro ao buscar eventos de hoje: {exc}"

    def get_upcoming_events(self, days: int = 7) -> str:
        if not self.is_available():
            return "Google Calendar não está disponível. Instale as dependências e configure as credenciais."
        service = self._calendar_service()
        if service is None:
            return "Não foi possível conectar ao Google Calendar."
        try:
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=days)
            result = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=20,
            ).execute()
            events = result.get("items", [])
            if not events:
                return f"Você não tem eventos nos próximos {days} dias."
            lines = [_format_event_for_voice(e) for e in events]
            return f"Nos próximos {days} dias você tem {len(events)} evento(s): " + "; ".join(lines) + "."
        except Exception as exc:
            return f"Erro ao buscar próximos eventos: {exc}"

    def get_next_event(self) -> str:
        if not self.is_available():
            return "Google Calendar não está disponível. Instale as dependências e configure as credenciais."
        service = self._calendar_service()
        if service is None:
            return "Não foi possível conectar ao Google Calendar."
        try:
            now = datetime.now(timezone.utc)
            result = service.events().list(
                calendarId="primary",
                timeMin=now.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=1,
            ).execute()
            events = result.get("items", [])
            if not events:
                return "Você não tem próximos eventos agendados."
            return "Seu próximo evento é: " + _format_event_for_voice(events[0]) + "."
        except Exception as exc:
            return f"Erro ao buscar próximo evento: {exc}"

    def get_unread_count(self) -> str:
        if not self.is_available():
            return "Gmail não está disponível. Instale as dependências e configure as credenciais."
        service = self._gmail_service()
        if service is None:
            return "Não foi possível conectar ao Gmail."
        try:
            result = service.users().labels().get(userId="me", id="INBOX").execute()
            count = result.get("messagesUnread", 0)
            if count == 0:
                return "Você não tem emails não lidos."
            elif count == 1:
                return "Você tem 1 email não lido."
            else:
                return f"Você tem {count} emails não lidos."
        except Exception as exc:
            return f"Erro ao verificar emails: {exc}"

    def get_recent_emails(self, limit: int = 5) -> str:
        if not self.is_available():
            return "Gmail não está disponível. Instale as dependências e configure as credenciais."
        service = self._gmail_service()
        if service is None:
            return "Não foi possível conectar ao Gmail."
        try:
            result = service.users().messages().list(
                userId="me", maxResults=limit, labelIds=["INBOX"]
            ).execute()
            messages = result.get("messages", [])
            if not messages:
                return "Nenhum email encontrado na caixa de entrada."
            summaries = []
            for msg in messages:
                msg_data = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject"]
                ).execute()
                headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
                sender = headers.get("From", "Remetente desconhecido")
                subject = headers.get("Subject", "Sem assunto")
                sender_name = sender.split("<")[0].strip().strip('"') or sender
                summaries.append(f"{sender_name}: {subject}")
            return f"Seus últimos {len(summaries)} emails: " + "; ".join(summaries) + "."
        except Exception as exc:
            return f"Erro ao buscar emails recentes: {exc}"

    def send_email(self, to: str, subject: str, body: str) -> str:
        if not self.is_available():
            return "Gmail não está disponível. Instale as dependências e configure as credenciais."
        return (
            f"CONFIRMAÇÃO NECESSÁRIA: Você deseja enviar um email para {to} "
            f"com o assunto '{subject}'? Diga 'confirmar envio' para prosseguir."
        )

    def _send_email_confirmed(self, to: str, subject: str, body: str) -> str:
        service = self._gmail_service()
        if service is None:
            return "Não foi possível conectar ao Gmail."
        try:
            import base64
            from email.mime.text import MIMEText
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"Email enviado com sucesso para {to}."
        except Exception as exc:
            return f"Erro ao enviar email: {exc}"

    def handle_voice_command(self, text: str) -> Optional[str]:
        lowered = text.lower()
        if any(phrase in lowered for phrase in ["agenda de hoje", "o que tenho hoje"]):
            return self.get_today_events()
        if any(phrase in lowered for phrase in ["próximos compromissos", "agenda da semana"]):
            return self.get_upcoming_events()
        if any(phrase in lowered for phrase in ["próximo evento", "quando é minha próxima reunião"]):
            return self.get_next_event()
        if any(phrase in lowered for phrase in ["quantos emails não lidos", "minha caixa de entrada"]):
            return self.get_unread_count()
        if any(phrase in lowered for phrase in ["últimos emails", "novos emails"]):
            return self.get_recent_emails()
        return None
