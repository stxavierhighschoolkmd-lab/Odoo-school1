import io
import logging
import struct
import datetime
from collections import deque
import uuid
from typing import Any, Union

from odoo.tools import mute_logger
from odoo.tools.pdf import (
    PdfFileReader,
    PdfObject,
    IndirectObject,
    NullObject,
    ArrayObject,
    DictionaryObject,
    NameObject,
    BooleanObject,
    NumberObject,
    TextStringObject,
    DecodedStreamObject as StreamObject,
)

from .constants import TrailerKeys as TK, PageAttributes as PG

_logger = logging.getLogger(__name__)


def b_(s: str | bytes) -> bytes:
    """ Converts string to bytes. Uses Latin-1 per PDF spec, falls back to UTF-8. """

    if isinstance(s, bytes):
        return s

    try:
        r = s.encode("latin-1")
    except UnicodeEncodeError:
        r = s.encode("utf-8")

    return r


class IndirectObjectsWrapper:
    """ Registry for tracking new PDF objects and their indirect references.
    Assigns IDs and resolves IndirectObjects safely.
    """

    def __init__(self, start_id=1) -> None:
        """
        :param start_id: Start ID. Set to the original PDF's /Size to prevent collisions.
        """
        self.objects_map = {}
        self.next_id = start_id

    def add_object(self, obj: PdfObject) -> IndirectObject:
        """ Registers a new object and points its indirect_reference attribute to itself. """
        self.objects_map[self.next_id] = obj
        obj.indirect_reference = IndirectObject(self.next_id, 0, self)
        self.next_id += 1

        return obj.indirect_reference

    def get_object(self, indirect_reference: Union[int, IndirectObject]) -> PdfObject:
        """ Resolves an indirect reference back to its underlying PDF raw object. """
        if isinstance(indirect_reference, int):
            obj = self.objects_map[indirect_reference]
        elif indirect_reference.pdf != self:
            raise ValueError("Wrapper must be self")
        else:
            obj = self.objects_map[indirect_reference.idnum]
        assert obj is not None, "mypy"
        return obj


class IncrementalPdfMerge:
    """ A utility class to perform an Incremental Update by merging an overlay PDF
    onto an existing PDF document.

    This class handles the low-level PDF structure required to append new content
    (such as a visual signature layer or stamp) to the end of a file without
    altering the original byte range. This approach ensures that the original
    document structure remains intact, which is essential for preserving existing
    digital signatures.

    The implementation follows the **Adobe PDF Reference (v1.7)** specifications
    for Incremental Updates, manually constructing the necessary:

    * **Indirect Objects:** For the new content streams and resources.
    * **Cross-Reference (XRef) Table:** To index the new objects.
    * **Trailer Dictionary:** To link the new update to the previous file version.

    (Ref: Adobe PDF Reference (v1.7) / https://ia601001.us.archive.org/1/items/pdf1.7/pdf_reference_1-7.pdf)

    :param pdf_raw: The binary content of the original PDF file.
    :type pdf_raw: bytes
    """

    def __init__(self, pdf_raw: bytes) -> None:
        """ Loads the PDF and seeks to EOF to prepare for appending modifications. """
        self.pdf_raw = pdf_raw
        self.output_stream = io.BytesIO(self.pdf_raw)
        self.output_stream.seek(0, io.SEEK_END)

    def get_output_stream(self) -> io.BytesIO:
        """ Returns the active stream pointing to the end of the PDF data. """
        return self.output_stream

    def get_output_stream_value(self) -> bytes:
        """ Returns the full binary content of the stream. """
        return self.output_stream.getvalue()

    def merge_pdf_as_annotation(
            self,
            overlay_pdf: PdfFileReader,
            overlay_pages: set[int] | None = None,
            annotations_title: str = "overlay"
    ) -> None:
        """ Merges the content of an overlay PDF onto the current PDF output stream.

        This method orchestrates an incremental update (Adobe PDF Reference, Sixth Edition,
        version 1.7 (2006), Section 3.4.5) to apply the overlay without rewriting the
        entire original file. The process involves:

        1. Loading the current PDF state from the active output stream.
        2. Merging the visual page content from the ``overlay_pdf`` onto the existing pages.
        3. Identifying all newly created or modified objects (e.g., updated page dictionaries).
        4. Writing the new objects and the updated XRef stream to the end of the file.

        :param overlay_pdf: A reader object containing the content to be overlaid.
            It must contain the same number of pages as the current PDF.
        :type overlay_pdf: PdfFileReader
        :param overlay_pages: Optional set of PDF page indices indicating which
            pages should receive the overlay.
        :type overlay_pages: set[int] or None
        :param annotations_title: The title or internal name assigned to the created
            annotation. This parameter is only utilized if ``merge_res_as_annotation``
            is set to ``True``. Defaults to "overlay".
        :type annotations_title: str
        :return: None
        """
        pdf_reader, incremented_objects = self._merge_pdf_pages_as_annotation(overlay_pdf, annotations_title, overlay_pages)

        self._write_incremented_pdf(pdf_reader, incremented_objects)

    def normalize_pages_annotations_to_indirect(self):
        """ Normalizes the ``/Annots`` array of every page into an indirect object,
        or creates it if it doesn't exist.

        This method sweeps the document, extracts direct arrays (or creates empty ones),
        assigns them unique object IDs, and updates the Page dictionaries to point
        to these new indirect references (e.g., ``/Annots 50 0 R``).

        This function runs as its own discrete incremental update.
        """

        pdf_reader = PdfFileReader(io.BytesIO(self.get_output_stream_value()), strict=False)
        incremented_objects = {}

        next_id = self._get_pdf_size(pdf_reader)

        for page_index in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_index]
            try:
                raw_annots = page.raw_get(PG.ANNOTS)
            except KeyError:
                raw_annots = None
            if not raw_annots or not isinstance(raw_annots, IndirectObject):
                if raw_annots is None:
                    raw_annots = ArrayObject()

                incremented_objects[next_id, 0] = raw_annots
                raw_annots_ref = IndirectObject(next_id, 0, None)
                page[NameObject(PG.ANNOTS)] = raw_annots_ref
                next_id += 1

                page_ref_id = page.indirect_reference.idnum
                page_ref_gen = page.indirect_reference.generation
                incremented_objects[page_ref_id, page_ref_gen] = page
                self.update_cached_indirect_object(pdf_reader, page_ref_gen, page_ref_id, page)

        self._write_incremented_pdf(pdf_reader, incremented_objects, False)

    def _merge_pdf_pages_as_annotation(
            self,
            overlay_pdf: PdfFileReader,
            annotations_title: str,
            overlay_pages: set[int] | None = None,
    ) -> tuple[PdfFileReader, dict[tuple[int, int], Any]]:
        """ Merges an overlay PDF onto the current PDF by embedding the overlay content
        as a locked Stamp Annotation.

        Instead of destructively merging the overlay directly into the base page's
        ``/Contents`` stream, this method uses a non-destructive approach
        (Adobe PDF Reference 1.7 (2006), Section 8.4). It encapsulates the overlay
        graphics into a discrete, locked layer. The structural process is as follows:

        :param overlay_pdf: A reader object containing the visual content to be stamped.
            It must contain the same number of pages as the current PDF.
        :type overlay_pdf: PdfFileReader
        :param annotations_title: The text title (``/T``) assigned to the stamp
            annotation, useful for identifying the overlay layer in PDF viewer UI.
            Defaults to "overlay".
        :type annotations_title: str
        :param overlay_pages: Optional set of PDF page indices indicating which
            pages should receive the overlay.
        :type overlay_pages: set[int] or None
        :return: A tuple containing the updated state:
            - The ``PdfFileReader`` instance representing the base document.
            - A dictionary of ``incremented_objects`` mapping ``(object_id, generation)``
              tuples to the modified PDF objects.
        :rtype: tuple[PdfFileReader, dict[tuple[int, int], Any]]
        """
        pdf_reader = PdfFileReader(io.BytesIO(self.get_output_stream_value()), strict=False)
        indirect_obj_wrapper = IndirectObjectsWrapper()  # A temporary Wrapper for new objects, useful for the indirect sweep
        incremented_objects = {}

        for page_index in range(len(pdf_reader.pages)):
            if overlay_pages and page_index not in overlay_pages:
                continue

            page = pdf_reader.pages[page_index]
            overlay_page = overlay_pdf.pages[page_index]

            content_stream = overlay_page.get_contents()
            if content_stream is None:
                continue

            overlay_resources = overlay_page.get(PG.RESOURCES, DictionaryObject())
            media_box = page.mediabox

            # Create the Appearance Stream XObject (Section 4.9): Extracts the raw content stream and
            # resources from the overlay page and wraps them in a Form XObject.
            appearance_stream = StreamObject()
            appearance_stream._data = content_stream.get_data()
            appearance_stream.update({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Form"),
                NameObject("/FormType"): NumberObject(1),
                NameObject("/BBox"): ArrayObject([
                    NumberObject(media_box.left), NumberObject(media_box.bottom),
                    NumberObject(media_box.right), NumberObject(media_box.top)
                ]),
                NameObject("/Resources"): overlay_resources
            })

            # Create the Stamp Annotation (Section 8.4.5): Create a ``/Stamp`` annotation
            # dictionary locked via ``/F 196`` (Print, NoZoom, NoRotate, ReadOnly),
            # ``/Locked``, and ``/LockedContents`` flags. It also injects essential
            # tracking metadata (``/NM`` UUID, ``/M`` modification date).
            appearance_stream_ref = indirect_obj_wrapper.add_object(appearance_stream)
            annot_dict = DictionaryObject()
            annot_dict.update({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Stamp"),
                NameObject("/T"): TextStringObject(f"{annotations_title}_page_{page_index}"),
                NameObject("/Rect"): ArrayObject([
                    NumberObject(media_box.left), NumberObject(media_box.bottom),
                    NumberObject(media_box.right), NumberObject(media_box.top)
                ]),
                NameObject("/F"): NumberObject(196),
                NameObject("/Locked"): BooleanObject(True),
                NameObject("/LockedContents"): BooleanObject(True),
                # Appearance Stream (Section 8.4.4): Assigns the Form XObject to the
                # normal appearance state (``/AP << /N ... >>``) of the annotation.
                NameObject("/AP"): DictionaryObject({
                    NameObject("/N"): appearance_stream_ref
                }),
                NameObject("/P"): page.indirect_reference,  # Anchor to the specific exact page reference
                NameObject("/NM"): TextStringObject(str(uuid.uuid4())),  # Unique UUID name to prevent orphaned detached states
                NameObject("/M"): TextStringObject(datetime.datetime.now(datetime.timezone.utc).strftime("D:%Y%m%d%H%M%SZ"))
            })

            # Attach the Annotation to the Original Page
            annot_ref = indirect_obj_wrapper.add_object(annot_dict)
            try:
                raw_annots = page.raw_get(PG.ANNOTS)
            except KeyError:
                raw_annots = None
            if raw_annots and isinstance(raw_annots, IndirectObject):
                annots_array = raw_annots.get_object()
                annots_array.append(annot_ref)
                raw_id = raw_annots.idnum
                raw_gen = raw_annots.generation
                if (raw_id, raw_gen) not in incremented_objects:
                    incremented_objects[raw_id, raw_gen] = annots_array
                self.update_cached_indirect_object(pdf_reader, raw_gen, raw_id, annots_array)
            else:
                if raw_annots is None:
                    raw_annots = ArrayObject()

                raw_annots.append(annot_ref)
                page[NameObject(PG.ANNOTS)] = raw_annots

                page_ref_id = page.indirect_reference.idnum
                page_ref_gen = page.indirect_reference.generation
                incremented_objects[page_ref_id, page_ref_gen] = page
                # Invalidate cache and cache new page reference so it would be seen while sweeping indirect references later on
                self.update_cached_indirect_object(pdf_reader, page_ref_gen, page_ref_id, page)

        return pdf_reader, incremented_objects

    @staticmethod
    def update_cached_indirect_object(pdf_reader: PdfFileReader, obj_gen: int, obj_id: int, obj: Any) -> None:
        """
        Caches an indirect object into the given PDF reader's internal cache.

        This method acts as a wrapper around the reader's `cache_indirect_object`
        method to intentionally suppress noisy "Overwriting cache" warnings
        generated by the PyPDF2 or pypdf libraries.

        :param pdf_reader: The PDF reader instance where the object will be cached.
        :param obj_gen: The generation number of the PDF indirect object.
        :param obj_id: The ID number of the PDF indirect object.
        :param obj: The actual PDF object data to be cached.
        :return: Does not return anything.
        """
        with mute_logger('PyPDF2'), mute_logger('pypdf'):
            pdf_reader.cache_indirect_object(obj_gen, obj_id, obj)

    def _write_incremented_pdf(self, pdf_reader, incremented_objects, sweep_new_indirect_objects=True):
        """ Finalizes the incremental update by writing modified objects and the trailer.

        **Execution Flow:**

        1.  **ID Resolution:** Determines the next available Object ID (`start_id`).
            It attempts to read the trailer ``/Size``; if missing (common in PDF 1.5+
            Object Streams), it calculates the max ID by scanning existing XRefs.
        2.  **Graph Traversal:** Recursively sweeps from the Catalog (`/Root`) to detect
            any *newly created* objects injected during the merge that weren't explicitly
            tracked.
        3.  **Object Writing:** Serializes all modified and new objects to the output stream.
        4.  **XRef & Trailer:** Generates the new Cross-Reference Table and Trailer dictionary,
            linking back to the ``original_startxref``.

        :param pdf_reader: The reader instance representing the current PDF state.
        :type pdf_reader: PdfFileReader
        :param incremented_objects: A dictionary mapping Object IDs to the Page objects
            that were explicitly modified during the merge.
        :type incremented_objects: dict[tuple[int, int], Any]
        :param sweep_new_indirect_objects: A flag indicating whether to perform a deep
            search of the document's object graph. When ``True``, it detects new or
            incremented ``IndirectObject`` instances that haven't been explicitly
            tracked, adding them to the incremented objects set.
        :type sweep_new_indirect_objects: bool
        :return: None
        """
        if incremented_objects is None or len(incremented_objects) == 0:
            return

        # Get xref start offset
        original_startxref = self._find_last_startxref(self.get_output_stream_value())

        # Check if the original PDF uses an XRef stream
        # PyPDF strips /Type /XRef from the trailer dict.
        # Check the raw bytes at original_startxref: if it does not start with 'xref',
        # it is an object representing an XRef stream
        is_xref_stream = pdf_reader.trailer.get(TK.TYPE) == "/XRef"
        if not is_xref_stream:
            raw_data = self.get_output_stream_value()
            target_bytes = raw_data[original_startxref:original_startxref + 20].lstrip()
            if target_bytes and not target_bytes.startswith(b"xref"):
                is_xref_stream = True

        size = self._get_pdf_size(pdf_reader)

        # We perform a recursive traversal starting from the Catalog (/Root) to
        # detect any newly created objects injected during the merge. These objects
        # are assigned valid, contiguous Object IDs to ensure they are correctly
        # indexed in the upcoming incremental XRef update. Additionally, this step
        # resolves circular references (e.g., objects pointing back to their parent
        # Pages), ensuring the integrity of the object graph.
        if sweep_new_indirect_objects:
            catalog = pdf_reader.trailer[TK.ROOT]
            new_objects = self._traverse_incremented_objects(pdf_reader, catalog, size)
            for key, val in new_objects.items():
                incremented_objects[key] = val

        # Write all objects to the output stream
        new_xref_entries = self._write_objects(incremented_objects)

        # construct the end of the PDF
        if is_xref_stream:
            self._write_xref_stream(pdf_reader, new_xref_entries, original_startxref, size)
        else:
            # Generate Xref table
            xref_start, max_entry_id = self._write_xref_table(new_xref_entries)
            new_size = max(size - 1, max_entry_id) + 1

            # Construct the PDF trailer
            self._write_trailer(pdf_reader, original_startxref, xref_start, new_size)

        return new_xref_entries

    def _get_pdf_size(self, pdf_reader):
        """ Returns the PDF /Size limit (highest object ID + 1).
        Calculates it mathematically if missing from the trailer.
        """
        # Trust that the trailer contain a size first (Standard behavior)
        size = pdf_reader.trailer.get(TK.SIZE)

        # If size is missing, it's a xref stream PDF, we need calculate size (Fall back for PDF 1.5+)
        if not size:
            # Gather IDs, defaulting to {0} to prevent max() crash on empty files
            all_ids = set(pdf_reader.xref_objStm.keys()) | {0}
            for gen in pdf_reader.xref.values():
                all_ids.update(gen.keys())
            size = max(all_ids) + 1

        return size

    def _write_objects(self, incremented_objects):
        """ Writes each incremented object block and returns its final byte offset mapping for the XRef. """
        output = self.output_stream
        output.write(b"\n")
        xref_entries = {}
        for (obj_id, obj_gen), obj_data in sorted(incremented_objects.items()):
            xref_entries[obj_id, obj_gen] = output.tell()
            output.write(b_(f"{obj_id} {obj_gen} obj"))
            obj_data.write_to_stream(output, None)
            output.write(b"\nendobj\n")

        return xref_entries

    def _write_xref_stream(self, pdf_reader, xref_entries, original_startxref, original_size):
        """ Writes a PDF 1.7 binary Cross-Reference (XRef) Stream for an incremental update.

        As defined in PDF Reference 1.7, Section 3.4.7, this replaces the older plain-text
        `xref` tables and trailer dictionary with a single binary stream object. It handles
        the structural requirements by:

        1. Grouping modified objects into contiguous chunks for the `/Index` array.
        2. Packing byte offsets into a binary payload using a `/W [1 4 2]` layout.
        3. Self-referencing the stream's own object ID and absolute byte offset.
        4. Merging core trailer entries (e.g., `/Root`) and maintaining the incremental
           update chain via the `/Prev` key (Section 3.4.5).

        :param pdf_reader: Original PDF reader to extract core trailer entries to carry forward.
        :type pdf_reader: PdfReader
        :param xref_entries: Maps `(object_id, generation)` to their new absolute byte offsets.
        :type xref_entries: dict[tuple[int, int], int]
        :param original_startxref: Absolute byte offset of the previous xref section to set the `/Prev` link.
        :type original_startxref: int
        :param original_size: The previous trailer's `/Size` value, used to assign this stream's ID and update total size.
        :type original_size: int
        """
        output = self.output_stream

        xref_start_offset = output.tell()

        # Object 0 (Sentinel Entry):
        if (0, 65535) not in xref_entries:
            xref_entries[0, 65535] = 0

        # Get maximum object ID from the new xref entries
        max_obj_id = max(k[0] for k in xref_entries)

        # Calculate the ID for this XRef stream as it will be written as a new object (next available ID)
        current_highest_id = max(original_size - 1, max_obj_id)
        xref_stream_obj_id = current_highest_id + 1

        # Add the XRef Stream itself to the xref entries
        # XRef streams always have a generation of 0
        xref_entries[xref_stream_obj_id, 0] = xref_start_offset

        # Prepare the Stream Data (Hex Encoded)
        sorted_ids = sorted(xref_entries.keys())
        index_array = []
        stream_data_hex = []

        i = 0
        while i < len(sorted_ids):
            start_j = i
            # Check contiguous chunks using the Object ID
            while i + 1 < len(sorted_ids) and sorted_ids[i + 1][0] == sorted_ids[i][0] + 1:
                i += 1

            chunk_ids = sorted_ids[start_j: i + 1]

            # Add to /Index array: [First Object ID, Count]
            index_array.append(chunk_ids[0][0])
            index_array.append(len(chunk_ids))

            # Generate Data for this chunk
            for oid_tuple in chunk_ids:
                oid, ogen = oid_tuple

                # Append the object entry to the xref stream data.
                # Format ">B I H" packs 7 bytes in Big-Endian order (required for PDF streams):
                #  > : Big-endian byte order
                #  B : Unsigned char (1 byte)   -> Entry Type (0, 1, or 2)
                #  I : Unsigned int (4 bytes)   -> Byte Offset (or Next Free Object ID)
                #  H : Unsigned short (2 bytes) -> Generation Number
                if oid == 0:
                    # Required sentinel entry (Object 0) for the free object linked list.
                    # Packs: [Type=0 (Free), Next_Free_Obj=0 (End of list), Max_Generation=65535]
                    stream_data_hex.append(struct.pack(">B I H", 0, 0, 65535))
                else:
                    offset = xref_entries[oid_tuple]

                    # Type 1 entries define objects that are in use but are not compressed
                    # Packs: [Type=1, Absolute_Byte_Offset, Generation_Number]
                    stream_data_hex.append(struct.pack(">B I H", 1, offset, ogen))
            i += 1

        # Join data as raw bytes
        stream_content_bytes = b"".join(stream_data_hex)

        stream_length = len(stream_content_bytes)

        xref_stream_object = StreamObject()
        xref_stream_object._data = stream_content_bytes
        xref_stream_object.update({
            NameObject(TK.TYPE): NameObject("/XRef"),
            NameObject(TK.SIZE): NumberObject(xref_stream_obj_id + 1),
            NameObject(TK.ROOT): pdf_reader.trailer.raw_get(TK.ROOT),
            NameObject(TK.PREV): NumberObject(original_startxref),

            # /W defines the byte widths for the 3 columns in the XRef stream: [Type, Offset, Generation]
            # - 1 byte for Type: The PDF spec only uses types 0, 1, and 2, which fit in one byte.
            # - 4 bytes for Offset: Supports byte offsets for PDFs up to ~4.29 GB.
            # - 2 bytes for Generation: Perfectly fits 65,535, the maximum allowed generation number.
            NameObject("/W"): ArrayObject([NumberObject(1), NumberObject(4), NumberObject(2)]),

            NameObject("/Index"): ArrayObject([NumberObject(x) for x in index_array]),
            NameObject("/Length"): NumberObject(stream_length)
        })
        if TK.INFO in pdf_reader.trailer:
            xref_stream_object[NameObject(TK.INFO)] = pdf_reader.trailer.raw_get(TK.INFO)
        if TK.ID in pdf_reader.trailer:
            xref_stream_object[NameObject(TK.ID)] = pdf_reader.trailer.raw_get(TK.ID)
        if TK.ENCRYPT in pdf_reader.trailer:
            xref_stream_object[NameObject(TK.ENCRYPT)] = pdf_reader.trailer.raw_get(TK.ENCRYPT)

        output.write(b_(f"{xref_stream_obj_id} 0 obj\n"))
        xref_stream_object.write_to_stream(output, None)
        output.write(b"\nendobj\n")

        # Trailer / EOF
        output.write(b_(f"startxref\n{xref_start_offset}\n%%EOF\n"))

    def _write_xref_table(self, xref_entries):
        """ Writes the Cross-Reference (XRef) table to the output stream. """
        output = self.output_stream

        # ------------------------------------------------------------------------------------------
        # XRef CONSTRUCTIONS (Adobe PDF Reference, Sixth Edition, version 1.7 (2006), Section 7.5.4)
        # ------------------------------------------------------------------------------------------
        # The PDF specification allows the cross-reference table to be split
        # into multiple subsections to support "sparse" Object ID ranges.
        #
        # This block identifies clusters of contiguous Object IDs (e.g., the
        # modified Page Object at ID 12, followed by a gap, then new Objects
        # 50-55) and writes a separate subsection header for each cluster.
        # ------------------------------------------------------------------------------------------
        xref_start = output.tell()
        output.write(b"xref\n")

        # Object 0 (Sentinel Entry):
        # The mandatory first entry of the XRef table. It acts as the head of the
        # linked list for deleted (free) objects.
        # - Offset 0000000000: Points to the next free object index (0 if none).
        # - Generation 65535: Max integer ensures Object 0 is never reused/allocated.
        # - Type 'f': Marks this entry as 'Free'.
        if (0, 65535) not in xref_entries:
            xref_entries[0, 65535] = 0

        sorted_ids = sorted(xref_entries.keys())
        i = 0
        while i < len(sorted_ids):
            start_j = i
            while i + 1 < len(sorted_ids) and sorted_ids[i + 1][0] == sorted_ids[i][0] + 1:
                i += 1

            chunk_ids = sorted_ids[start_j: i + 1]
            start_id = chunk_ids[0][0]
            output.write(b_(f"{start_id} {len(chunk_ids)}\n"))
            for obj_tuple in chunk_ids:
                oid, ogen = obj_tuple
                if oid == 0:
                    output.write(b_(f"{0:0>10} {65535:0>5} f \n"))
                else:
                    offset = xref_entries[obj_tuple]
                    output.write(b_(f"{offset:0>10} {ogen:0>5} n \n"))

            i += 1

        return xref_start, sorted_ids[-1][0]

    def _write_trailer(self, pdf_reader, original_startxref, xref_start, size):
        """ Writes the trailer dictionary and the final end-of-file markers.

        :param pdf_reader: The reader instance, used to copy original Root, Info, and ID.
        :param original_startxref: The byte offset of the previous XRef table (for the ``/Prev`` chain).
        :param xref_start: The byte offset of the newly written XRef table.
        :param size: The total number of objects in the updated PDF.
        :return: None
        """
        output = self.output_stream

        # --------------------------------------------------------------------------------------------
        # TRAILER CONSTRUCTION (Adobe PDF Reference, Sixth Edition, version 1.7 (2006), Section 7.5.5)
        # --------------------------------------------------------------------------------------------
        # The trailer dictionary allows the PDF reader to quickly locate key
        # document structures. For an Incremental Update, it must:
        # 1. Point to the Catalog (/Root) and Metadata (/Info) of the original file.
        # 2. Define the total number of objects (/Size) including the new additions.
        # 3. Chain back to the previous XRef table via the /Prev key, preserving
        #    the document's revision history.
        # 4. Replicate critical security identifiers (/ID and /Encrypt) to maintain
        #    file integrity and access permissions.
        # --------------------------------------------------------------------------------------------
        output.write(b"trailer\n")
        trailer = DictionaryObject()
        trailer.update(
            {
                NameObject(TK.SIZE): NumberObject(size),
                NameObject(TK.ROOT): pdf_reader.trailer.raw_get(TK.ROOT),
                NameObject(TK.PREV): NumberObject(original_startxref)
            }
        )
        if TK.INFO in pdf_reader.trailer:
            trailer[NameObject(TK.INFO)] = pdf_reader.trailer.raw_get(TK.INFO)
        if TK.ID in pdf_reader.trailer:
            trailer[NameObject(TK.ID)] = pdf_reader.trailer.raw_get(TK.ID)
        if TK.ENCRYPT in pdf_reader.trailer:
            trailer[NameObject(TK.ENCRYPT)] = pdf_reader.trailer.raw_get(TK.ENCRYPT)

        trailer.write_to_stream(output, None)
        output.write(b_(f"\nstartxref\n{xref_start}\n%%EOF\n"))  # EOF

    def _find_last_startxref(self, data):
        """ Scans backwards to find the byte offset of the previously saved XRef block. """
        # Search from end of file for startxref
        idx = data.rfind(b"startxref")
        if idx == -1:
            return 0

        return int(data[idx:].splitlines()[1].strip())

    def _traverse_incremented_objects(self, pdf_reader: PdfFileReader, root, next_id) -> dict[tuple[int, int], Any]:
        """ Recursively traverses the PDF object graph to identify new objects and update
        references.

        This method performs a **Depth-First Search (DFS)** starting from the provided
        ``root`` object. Its primary goals are:

        1.  **Discovery:** Identify all reachable objects (dictionaries, arrays, streams).
        2.  **Resolution:** Differentiate between existing objects (from the original PDF)
            and new objects (from the overlay).
        3.  **Remapping:** Assign valid Object IDs to new objects using ``_resolve_indirect_object``.
        4.  **Pointer Fixup:** If a child object is remapped to a new ID, this method updates
            the parent container (Dictionary or Array) to point to the new reference.

        It uses an iterative stack-based approach (instead of recursion) to prevent
        stack overflow errors on deeply nested PDFs.

        :param pdf_reader: The reader instance for the original source PDF.
        :type pdf_reader: PdfFileReader
        :param root: The starting point of the traversal (usually the Document Catalog).
        :type root: DictionaryObject or ArrayObject
        :param next_id: The first available Object ID to use for new objects.
        :type next_id: int
        :return: Newly added objects dict to be incremented at the end of the pdf
        :rtype: dict[tuple[int, int], Any]
        """
        incremented_objects = {}

        idnum_hash = {}
        stack = deque()
        discovered = set()
        parent = None
        grant_parents = []
        key_or_id = None

        # Start from root
        stack.append((root, parent, key_or_id, grant_parents))

        while len(stack):
            data, parent, key_or_id, grant_parents = stack.pop()

            # Build stack for a processing depth-first
            if isinstance(data, DictionaryObject):
                for key, value in list(data.items()):
                    stack.append(
                        (
                            value,
                            data,
                            key,
                            grant_parents + [parent] if parent is not None else [],
                        )
                    )
            elif isinstance(data, ArrayObject):
                for idx in range(len(data)):
                    value = data[idx]
                    stack.append(
                        (
                            value,
                            data,
                            idx,
                            grant_parents + [parent] if parent is not None else [],
                        )
                    )
            elif isinstance(data, IndirectObject):
                data, next_id = self._resolve_indirect_object(pdf_reader, data, idnum_hash, incremented_objects, next_id)

                data_key = (data.idnum, data.generation)
                if data_key not in discovered:
                    discovered.add(data_key)
                    real_obj = self._get_indirect_object_data(data, incremented_objects)
                    stack.append((real_obj, None, None, []))

            # Check if data has a parent and if it is a dict or an array update the value
            if isinstance(parent, (DictionaryObject, ArrayObject)):
                if isinstance(data, StreamObject):
                    # a dictionary value is a stream.  streams must be indirect
                    # objects, so we need to change this value.
                    incremented_objects[next_id, 0] = data
                    data_hash = data.hash_value()
                    idnum_hash[data_hash] = IndirectObject(next_id, 0, None)
                    next_id += 1
                    data = idnum_hash[data_hash]

                update_hashes = []

                # Data changed and thus the hash value changed
                old_data = parent[key_or_id] if isinstance(parent, ArrayObject) else parent.raw_get(key_or_id)
                if old_data != data:
                    update_hashes = [parent.hash_value()] + [
                        grant_parent.hash_value() for grant_parent in grant_parents
                    ]
                    parent[key_or_id] = data

                # Update old hash value to new hash value
                for old_hash in update_hashes:
                    indirect_reference = idnum_hash.pop(old_hash, None)

                    if indirect_reference is not None:
                        indirect_reference_obj = self._get_indirect_object_data(indirect_reference, incremented_objects)

                        if indirect_reference_obj is not None:
                            idnum_hash[
                                indirect_reference_obj.hash_value()
                            ] = indirect_reference

        return incremented_objects

    def _resolve_indirect_object(
            self,
            pdf_reader: PdfFileReader,
            data: IndirectObject,
            idnum_hash: dict[bytes, Any],
            incremented_objects: dict[tuple[int, int], Any],
            next_id: int
    ) -> IndirectObject:
        """ Resolves an indirect reference to its concrete object and determines its final Object ID.

        This method acts as a router/deduplicator:

        * **Existing Objects:** If the object belongs to ``pdf_reader`` (the original file),
            it preserves the original Object ID.
        * **New Objects:** If the object is foreign (from the overlay PDF), it assigns a
            new, unique Object ID (``next_id``), registers it in ``incremented_objects``,
            and increments the counter.
        * **Deduplication:** Uses ``idnum_hash`` to ensure that identical objects are
            reused rather than duplicated in the output file.

        :param data: The indirect reference to resolve.
        :type data: IndirectObject
        :param pdf_reader: The reader for the original PDF.
        :param idnum_hash: A cache dictionary mapping object hashes to their resolved IndirectObjects.
        :param incremented_objects: The registry of new objects for the incremental update.
        :param next_id: The next available Object ID.
        :return: A tuple containing the resolved ``IndirectObject`` and the (possibly incremented) ``next_id``.
        :rtype: tuple[IndirectObject, int]
        :raises ValueError: If the underlying PDF stream is closed.
        """
        if hasattr(data.pdf, "stream") and data.pdf.stream.closed:
            raise ValueError(f"I/O operation on closed file: {data.pdf.stream.name}")

        real_obj = self._get_indirect_object_data(data, incremented_objects)

        if real_obj is None:
            _logger.warning(
                "Unable to resolve [%s: %s], returning NullObject instead",
                data.__class__.__name__,
                data,
            )
            real_obj = NullObject()

        hash_value = real_obj.hash_value()

        if hash_value in idnum_hash:
            return idnum_hash[hash_value], next_id

        if data.pdf == pdf_reader:
            idnum_hash[hash_value] = IndirectObject(data.idnum, 0, pdf_reader)
        else:  # This is new incremented object in this PDF
            incremented_objects[next_id, 0] = real_obj
            idnum_hash[hash_value] = IndirectObject(next_id, 0, None)
            next_id += 1

        return idnum_hash[hash_value], next_id

    def _get_indirect_object_data(self, indirect_obj, incremented_objects):
        """ Resolves an indirect reference into its underlying PDF object.

        Retrieves the actual data by checking two locations:
        1. Original PDF: Fetches via `indirect_obj.pdf` if tied to an existing document.
        2. Incremented Objects: Falls back to the `incremented_objects` dictionary
           for new or modified objects not tied to a reader.
        """
        if indirect_obj.pdf:
            return indirect_obj.pdf.get_object(indirect_obj)
        else:
            return incremented_objects[indirect_obj.idnum, indirect_obj.generation]
