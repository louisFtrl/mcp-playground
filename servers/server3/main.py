from mcp.server.fastmcp import FastMCP
from typing import List, Optional
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from datetime import datetime, timedelta
import pytz

mcp = FastMCP("Google Drive MCP", host="0.0.0.0", port=8002)

@mcp.tool()
async def list_drive_files(
    access_token: str,
    query: Optional[str] = None,
    page_size: int = 10,
    mime_type: Optional[str] = None
) -> List[dict]:
    """List files from a user's Google Drive.

    Args:
        access_token: OAuth2 token for Google Drive access.
        query: Search query for filtering files.
        page_size: Max number of files to return.
        mime_type: Filter files by MIME type.

    Returns:
        A list of file metadata.
    """
    creds = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=creds)

    q = query if query else ''
    if mime_type:
        q += f" mimeType='{mime_type}'"

    results = service.files().list(
        q=q.strip(),
        pageSize=page_size,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()

    files = results.get('files', [])
    return files

@mcp.tool()
async def get_file_metadata(access_token: str, file_id: str) -> dict:
    """Retrieve metadata of a specific file.

    Args:
        access_token: OAuth2 token for Google Drive.
        file_id: ID of the file.

    Returns:
        Metadata of the file.
    """
    creds = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=creds)

    file = service.files().get(fileId=file_id, fields="id, name, mimeType, size, modifiedTime").execute()
    return file

@mcp.tool()
async def list_google_docs(
    access_token: str,
    page_size: int = 10
) -> list:
    """
    Liste les fichiers Google Docs dans Google Drive.

    Args:
        access_token: OAuth2 token Google.
        page_size: Nombre maximum de fichiers à retourner.

    Returns:
        Liste de dictionnaires contenant les métadonnées des Google Docs.
    """
    creds = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=creds)

    results = service.files().list(
        q="mimeType='application/vnd.google-apps.document'",
        pageSize=page_size,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()

    return results.get('files', [])

@mcp.tool()
async def get_google_doc_content(access_token: str, document_id: str) -> str:
    """
    Récupère le contenu texte brut d'un Google Doc.

    Args:
        access_token: OAuth2 token Google.
        document_id: ID du document Google Docs.

    Returns:
        Contenu texte concaténé du document.
    """
    creds = Credentials(token=access_token)
    docs_service = build('docs', 'v1', credentials=creds)

    doc = docs_service.documents().get(documentId=document_id).execute()
    content = []

    for element in doc.get('body', {}).get('content', []):
        paragraph = element.get('paragraph')
        if not paragraph:
            continue
        for elem in paragraph.get('elements', []):
            text_run = elem.get('textRun')
            if text_run:
                content.append(text_run.get('content', ''))

    return ''.join(content)

@mcp.tool()
async def list_gmail_messages(
    access_token: str,
    query: Optional[str] = None,
    max_results: int = 10
) -> List[dict]:
    """
    Liste les derniers emails de la boîte Gmail de l'utilisateur.

    Args:
        access_token: OAuth2 token Google.
        query: Requête de recherche Gmail (ex: 'is:unread', 'from:example@gmail.com', etc.).
        max_results: Nombre maximum de messages à récupérer.

    Returns:
        Une liste contenant les métadonnées des emails (id, sujet, expéditeur, date).
    """
    creds = Credentials(token=access_token)
    gmail_service = build('gmail', 'v1', credentials=creds)

    messages_result = gmail_service.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_results
    ).execute()

    messages = messages_result.get('messages', [])
    emails = []

    for msg in messages:
        msg_detail = gmail_service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['Subject', 'From', 'Date']
        ).execute()

        headers = {h['name']: h['value'] for h in msg_detail.get('payload', {}).get('headers', [])}
        email_data = {
            'id': msg['id'],
            'subject': headers.get('Subject', ''),
            'from': headers.get('From', ''),
            'date': headers.get('Date', '')
        }
        emails.append(email_data)

    return emails

@mcp.tool()
async def get_gmail_message_content(access_token: str, message_id: str) -> dict:
    """
    Récupère le contenu texte brut d'un email Gmail à partir de son ID.

    Args:
        access_token: OAuth2 token Google.
        message_id: ID du message Gmail.

    Returns:
        Un dictionnaire contenant le sujet, l'expéditeur, la date et le contenu texte brut de l'email.
    """
    creds = Credentials(token=access_token)
    gmail_service = build('gmail', 'v1', credentials=creds)

    message = gmail_service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()

    headers = {h['name']: h['value'] for h in message.get('payload', {}).get('headers', [])}
    subject = headers.get('Subject', '')
    sender = headers.get('From', '')
    date = headers.get('Date', '')

    def extract_text(payload):
        if payload.get('mimeType') == 'text/plain' and 'data' in payload['body']:
            import base64
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
        elif 'parts' in payload:
            for part in payload['parts']:
                text = extract_text(part)
                if text:
                    return text
        return None

    content = extract_text(message.get('payload', {})) or ''

    return {
        'subject': subject,
        'from': sender,
        'date': date,
        'content': content.strip()
    }

@mcp.tool()
async def list_google_slides_presentations(access_token: str, page_size: int = 10) -> list:
    """
    Liste les présentations Google Slides dans le Google Drive de l'utilisateur.

    Args:
        access_token: OAuth2 token Google.
        page_size: Nombre maximum de présentations à retourner.

    Returns:
        Une liste contenant les métadonnées des présentations.
    """
    creds = Credentials(token=access_token)
    drive_service = build('drive', 'v3', credentials=creds)

    query = "mimeType='application/vnd.google-apps.presentation'"

    results = drive_service.files().list(
        q=query,
        pageSize=page_size,
        fields="files(id, name, modifiedTime, owners, webViewLink)"
    ).execute()

    presentations = results.get('files', [])
    return presentations

@mcp.tool()
async def get_google_slides_content(access_token: str, presentation_id: str) -> str:
    """
    Récupère le contenu texte de toutes les diapositives d'une présentation Google Slides.

    Args:
        access_token: OAuth2 token Google.
        presentation_id: ID de la présentation Google Slides.

    Returns:
        Le texte concaténé de toutes les diapositives.
    """
    creds = Credentials(token=access_token)
    slides_service = build('slides', 'v1', credentials=creds)

    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    content = []

    for slide in presentation.get('slides', []):
        for element in slide.get('pageElements', []):
            shape = element.get('shape')
            if shape and 'text' in shape:
                text_elements = shape['text'].get('textElements', [])
                for text_elem in text_elements:
                    text_run = text_elem.get('textRun')
                    if text_run:
                        content.append(text_run.get('content', ''))

    return ''.join(content)

@mcp.tool()
async def list_google_sheets(
    access_token: str,
    page_size: int = 10
) -> List[dict]:
    """
    Liste les fichiers Google Sheets dans Google Drive.

    Args:
        access_token: OAuth2 token Google.
        page_size: Nombre maximal de fichiers à renvoyer.

    Returns:
        Une liste contenant les métadonnées des fichiers Sheets.
    """
    creds = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=creds)

    query = "mimeType='application/vnd.google-apps.spreadsheet'"

    results = service.files().list(
        q=query,
        pageSize=page_size,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()

    files = results.get('files', [])
    return files

@mcp.tool()
async def get_google_sheet_content(
    access_token: str,
    spreadsheet_id: str
) -> dict:
    """
    Récupère le contenu de toutes les feuilles d'un Google Sheets.

    Args:
        access_token: OAuth2 token Google.
        spreadsheet_id: ID du fichier Google Sheets.

    Returns:
        Un dictionnaire où chaque clé est le nom d'une feuille et chaque valeur est une liste de lignes (chaque ligne étant une liste de cellules).
    """
    creds = Credentials(token=access_token)
    service = build('sheets', 'v4', credentials=creds)

    # Récupérer les métadonnées du spreadsheet pour obtenir les noms des feuilles
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = spreadsheet.get('sheets', [])

    content = {}

    for sheet in sheets:
        sheet_title = sheet['properties']['title']
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_title
        ).execute()

        values = result.get('values', [])
        content[sheet_title] = values

    return content

@mcp.tool()
async def list_calendar_events(
    access_token: str,
    start_date: Optional[str] = None,  # format "YYYY-MM-DD"
    end_date: Optional[str] = None     # format "YYYY-MM-DD"
) -> List[dict]:
    """
    Liste les événements du calendrier Google dans une période donnée.
    Par défaut, la période est la semaine en cours (lundi à dimanche).

    Args:
        access_token: OAuth2 token Google.
        start_date: Date de début au format ISO "YYYY-MM-DD" (optionnel).
        end_date: Date de fin au format ISO "YYYY-MM-DD" (optionnel).

    Returns:
        Liste des événements avec id, summary, start, end.
    """
    creds = Credentials(token=access_token)
    service = build('calendar', 'v3', credentials=creds)

    # Fuseau horaire Paris
    paris_tz = pytz.timezone("Europe/Paris")
    today = datetime.now(paris_tz).date()

    # Calcul de la semaine en cours (lundi -> dimanche)
    if not start_date or not end_date:
        start_of_week = today - timedelta(days=today.weekday())  # lundi
        end_of_week = start_of_week + timedelta(days=6)           # dimanche
    else:
        start_of_week = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_of_week = datetime.strptime(end_date, "%Y-%m-%d").date()

    # Convertir en RFC3339 datetime avec timezone
    time_min = paris_tz.localize(datetime.combine(start_of_week, datetime.min.time())).isoformat()
    time_max = paris_tz.localize(datetime.combine(end_of_week, datetime.max.time())).isoformat()

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    # Format minimal des événements à retourner
    result = []
    for event in events:
        result.append({
            "id": event.get("id"),
            "summary": event.get("summary"),
            "start": event.get("start"),
            "end": event.get("end"),
        })

    return result

@mcp.tool()
async def get_calendar_event(access_token: str, event_id: str) -> dict:
    """
    Récupère les détails complets d'un événement Google Calendar.

    Args:
        access_token: OAuth2 token Google.
        event_id: ID de l'événement.

    Returns:
        Dictionnaire contenant les informations complètes de l'événement.
    """
    creds = Credentials(token=access_token)
    service = build('calendar', 'v3', credentials=creds)

    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    return event

if __name__ == "__main__":
    print("Starting Google Drive MCP server on port 8000...")
    print("Connect to this server using http://localhost:8000/sse")
    mcp.run(transport="sse")
