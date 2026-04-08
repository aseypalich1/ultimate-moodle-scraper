import html
import json
import urllib.parse
from typing import Dict, List

from moodle_dl.config import ConfigHelper
from moodle_dl.moodle.mods import MoodleMod
from moodle_dl.types import Course, File


class BookMod(MoodleMod):
    MOD_NAME = 'book'
    MOD_PLURAL_NAME = 'books'
    MOD_MIN_VERSION = 2015111600  # 3.0

    @classmethod
    def download_condition(cls, config: ConfigHelper, file: File) -> bool:
        return config.get_download_books() or (not (file.module_modname.endswith(cls.MOD_NAME) and file.deleted))

    async def real_fetch_mod_entries(
        self, courses: List[Course], core_contents: Dict[int, List[Dict]]
    ) -> Dict[int, Dict[int, Dict]]:

        result = {}
        if not self.config.get_download_books():
            return result

        books = (
            await self.client.async_post(
                'mod_book_get_books_by_courses', self.get_data_for_mod_entries_endpoint(courses)
            )
        ).get('books', [])

        for book in books:
            course_id = book.get('course', 0)
            module_id = book.get('coursemodule', 0)
            book_name = book.get('name', 'unnamed book')

            book_files = book.get('introfiles', [])
            self.set_props_of_files(book_files, type='book_file')

            book_intro = book.get('intro', '')
            if book_intro != '':
                book_files.append(
                    {
                        'filename': 'Book intro',
                        'filepath': '/',
                        'description': book_intro,
                        'type': 'description',
                    }
                )

            book_contents = self.get_module_in_core_contents(course_id, module_id, core_contents).get('contents', [])
            if len(book_contents) > 1:
                if self.config.get_enable_mhtml_capture():
                    # Capture each chapter as a full rendered MHTML page via Playwright
                    for chapter_content in book_contents[1:]:
                        chapter_path = chapter_content.get('filepath', '/')
                        # filepath is "/{chapterid}/" — extract the numeric ID
                        chapter_id = chapter_path.strip('/').split('/')[0]
                        if chapter_id.isdigit():
                            view_url = (
                                f'{self.client.url_base}mod/book/view.php'
                                f'?id={module_id}&chapterid={chapter_id}'
                            )
                        else:
                            # Fallback: use the original fileurl
                            view_url = chapter_content.get('fileurl', '')

                        chapter_name = chapter_content.get('filename', f'Chapter {chapter_id}')
                        # Strip any existing extension and use .mhtml
                        chapter_stem = chapter_name.rsplit('.', 1)[0] if '.' in chapter_name else chapter_name
                        mhtml_filename = f'{chapter_stem}.mhtml'

                        book_files.append(
                            {
                                'filename': mhtml_filename,
                                'filepath': chapter_content.get('filepath', '/'),
                                'fileurl': view_url,
                                'filesize': 0,
                                'timecreated': chapter_content.get('timecreated', 0),
                                'timemodified': chapter_content.get('timemodified', 0),
                                'type': 'mhtml',
                                'no_hash': True,
                            }
                        )
                else:
                    book_files += book_contents[1:]

            if len(book_contents) > 0:
                # Generate Table of Contents
                book_toc = json.loads(book_contents[0].get('content', ''))

                toc_html = '''
<!DOCTYPE html>
<html>
    <head>
        <style>
            ol {
                counter-reset: item
            }
            li {
                display: block
            }
            li:before {
                content: counters(item, ".")" ";
                counter-increment: item
            }
        </style>
    </head>
    <body>
        '''
                toc_html += self.create_ordered_index(book_toc)
                toc_html += '''
    </body>
</html>
                '''

                book_files.append(
                    {
                        'filename': 'Table of Contents',
                        'filepath': '/',
                        'timemodified': book.get('timemodified', 0),
                        'html': toc_html,
                        'type': 'html',
                        'no_search_for_urls': True,
                        'filesize': len(toc_html),
                    }
                )

            self.add_module(
                result,
                course_id,
                module_id,
                {
                    'id': book.get('id', 0),
                    'name': book_name,
                    'files': book_files,
                },
            )

        return result

    @staticmethod
    def create_ordered_index(items: List[Dict]) -> str:
        result = '<ol>\n'
        for entry in items:
            chapter_title = html.escape(entry.get("title", "untitled"))
            chapter_href = urllib.parse.quote(entry.get("href", "#failed"))
            result += f'<li><a title="{chapter_title}" href="{chapter_href}">{chapter_title}</a></li>\n'
            subitems = entry.get('subitems', [])
            if len(subitems) > 0:
                result += BookMod.create_ordered_index(subitems)

        result += '</ol>'
        return result
