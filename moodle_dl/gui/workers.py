import asyncio
import logging
import traceback

from PySide6.QtCore import QThread, Signal

from moodle_dl.config import ConfigHelper
from moodle_dl.database import StateRecorder
from moodle_dl.downloader.download_service import DownloadService
from moodle_dl.moodle.core_handler import CoreHandler
from moodle_dl.moodle.moodle_service import MoodleService
from moodle_dl.moodle.request_helper import RequestHelper
from moodle_dl.types import MoodleDlOpts


class AsyncWorker(QThread):
    """Base class for workers that run asyncio coroutines in a dedicated thread."""

    error_occurred = Signal(str)

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.do_work())
        except Exception as e:
            logging.error('Worker error (%s): %s', type(e).__name__, e)
            logging.debug(traceback.format_exc())
            self.error_occurred.emit(str(e))
        finally:
            loop.close()

    async def do_work(self) -> None:
        raise NotImplementedError


class LoginWorker(AsyncWorker):
    """Performs username/password login to obtain a Moodle token."""

    login_successful = Signal()
    login_failed = Signal(str)

    def __init__(self, config: ConfigHelper, opts: MoodleDlOpts, moodle_url, username: str, password: str) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self.moodle_url = moodle_url
        self.username = username
        self.password = password

    async def do_work(self) -> None:
        try:
            service = MoodleService(self.config, self.opts)
            token, privatetoken = service.obtain_login_token(self.username, self.password, self.moodle_url)
            self.config.set_moodle_URL(self.moodle_url)
            self.config.set_tokens(token, privatetoken)
            self.login_successful.emit()
        except (RuntimeError, ValueError, ConnectionError) as e:
            self.login_failed.emit(str(e))
        except Exception as e:
            self.login_failed.emit(f'{type(e).__name__}: {e}')


class SSOTokenWorker(AsyncWorker):
    """Extracts and saves token from SSO callback URL."""

    login_successful = Signal()
    login_failed = Signal(str)

    def __init__(self, config: ConfigHelper, opts: MoodleDlOpts, moodle_url, callback_url: str) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self.moodle_url = moodle_url
        self.callback_url = callback_url

    async def do_work(self) -> None:
        try:
            result = MoodleService.extract_token(self.callback_url)
            if result is None:
                self.login_failed.emit('Could not extract token from SSO response.')
                return
            token, privatetoken = result
            self.config.set_moodle_URL(self.moodle_url)
            self.config.set_tokens(token, privatetoken)
            self.login_successful.emit()
        except (RuntimeError, ValueError) as e:
            self.login_failed.emit(str(e))
        except Exception as e:
            self.login_failed.emit(f'{type(e).__name__}: {e}')


class FetchCoursesWorker(AsyncWorker):
    """Fetches the list of courses available to the user."""

    courses_fetched = Signal(list)

    def __init__(self, config: ConfigHelper, opts: MoodleDlOpts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts

    async def do_work(self) -> None:
        try:
            token = self.config.get_token()
            moodle_url = self.config.get_moodle_URL()
            request_helper = RequestHelper(self.config, self.opts, moodle_url, token)
            core_handler = CoreHandler(request_helper)

            service = MoodleService(self.config, self.opts)
            user_id, version = service.get_user_id_and_version(core_handler)

            courses_list = core_handler.fetch_courses(user_id)
            result = []
            for c in courses_list:
                result.append({'id': c.id, 'fullname': c.fullname})
            self.courses_fetched.emit(result)
        except (ConnectionError, ValueError, RuntimeError) as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            self.error_occurred.emit(f'{type(e).__name__}: {e}')


class FetchWorker(AsyncWorker):
    """Fetches current Moodle state and emits changed courses for preview."""

    fetch_finished = Signal(list, object)  # emits (changed_courses, database)

    def __init__(self, config: ConfigHelper, opts: MoodleDlOpts) -> None:
        super().__init__()
        self.config = config
        self.opts = opts

    async def do_work(self) -> None:
        moodle = MoodleService(self.config, self.opts)
        database = StateRecorder(self.config, self.opts)

        logging.info('Checking for changes...')
        changed_courses = await moodle.fetch_state(database)

        self.fetch_finished.emit(changed_courses, database)


class DownloadWorker(AsyncWorker):
    """Runs the download pipeline with pre-fetched courses and database."""

    download_started = Signal(object)  # emits the DownloadService instance
    download_finished = Signal(list)  # emits list of failed task descriptions
    progress_update = Signal(object)  # emits DownloadStatus

    def __init__(self, config: ConfigHelper, opts: MoodleDlOpts, changed_courses: list, database: object) -> None:
        super().__init__()
        self.config = config
        self.opts = opts
        self.changed_courses = changed_courses
        self.database = database
        self.download_service = None
        self._cancel_requested = False

    async def do_work(self) -> None:
        try:
            if self.opts.without_downloading_files:
                from moodle_dl.downloader.fake_download_service import (
                    FakeDownloadService,
                )

                self.download_service = FakeDownloadService(self.changed_courses, self.config, self.opts, self.database)
            else:
                self.download_service = DownloadService(self.changed_courses, self.config, self.opts, self.database)

            self.download_started.emit(self.download_service)

            await self.download_service.real_run()

            failed = []
            for task in self.download_service.get_failed_tasks():
                failed.append(f'{task.file.content_filename}: {task.status.get_error_text()}')

            self.download_finished.emit(failed)
        except (ConnectionError, ValueError, RuntimeError) as e:
            self.error_occurred.emit(str(e))
        except Exception as e:
            self.error_occurred.emit(f'{type(e).__name__}: {e}')

    def request_cancel(self) -> None:
        """Request cancellation of all downloads."""
        self._cancel_requested = True
        if self.download_service is not None:
            # Snapshot task list to avoid race with worker thread
            tasks = list(self.download_service.all_tasks)
            for task in tasks:
                task.status.skip_requested = True


class TestTelegramWorker(AsyncWorker):
    """Sends a test message via Telegram."""

    test_successful = Signal()
    test_failed = Signal(str)

    def __init__(self, token: str, chat_id: str) -> None:
        super().__init__()
        self.token = token
        self.chat_id = chat_id

    async def do_work(self) -> None:
        try:
            from moodle_dl.notifications.telegram.telegram_shooter import (
                TelegramShooter,
            )

            shooter = TelegramShooter(self.token, self.chat_id)
            shooter.send('Moodle-DL GUI: Test message')
            self.test_successful.emit()
        except Exception as e:
            self.test_failed.emit(str(e))


class TestDiscordWorker(AsyncWorker):
    """Sends a test message via Discord."""

    test_successful = Signal()
    test_failed = Signal(str)

    def __init__(self, webhook_urls: list) -> None:
        super().__init__()
        self.webhook_urls = webhook_urls

    async def do_work(self) -> None:
        try:
            from moodle_dl.notifications.discord.discord_shooter import DiscordShooter

            shooter = DiscordShooter(self.webhook_urls)
            shooter.send_msg('Moodle-DL GUI: Test message')
            self.test_successful.emit()
        except Exception as e:
            self.test_failed.emit(str(e))
