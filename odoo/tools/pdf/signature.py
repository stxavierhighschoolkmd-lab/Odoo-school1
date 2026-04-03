import datetime
import hashlib
import io
from typing import Any
from asn1crypto import cms, algos, core, x509
import logging

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
    from cryptography.hazmat.primitives.serialization import Encoding, load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.x509 import Certificate, load_pem_x509_certificates
except ImportError:
    # cryptography 41.0.7 and above is supported
    hashes = None
    PrivateKeyTypes = None
    Encoding = None
    load_pem_private_key = None
    padding = None
    Certificate = None
    load_pem_x509_certificates = None

from odoo.addons.base.models.res_company import ResCompany
from odoo.addons.base.models.res_users import ResUsers
from odoo.tools.pdf import (
    PdfFileReader,
    IndirectObject,
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    ByteStringObject,
    DecodedStreamObject as StreamObject,
    create_string_object
)

from .incremental_pdf_merge import IncrementalPdfMerge, IndirectObjectsWrapper
from .constants import TrailerKeys as TK, PageAttributes as PG, CatalogDictionary as CD, InteractiveFormDictEntries as IF

_logger = logging.getLogger(__name__)


class PdfSigner:
    """
    Manages the cryptographic signing of PDF documents using incremental updates.

    This class implements the **PAdES** (PDF Advanced Electronic Signatures) standard basics.
    It performs the following operations:

    1.  **Modification:** Modifies the document by adding a signature field via a form
        (AcroForm) and optionally merges a visual overlay.
    2.  **Signing:** Computes a cryptographic signature (PKCS#7/CMS).
    3.  **Injection:** Inserts the signature into the file without invalidating existing
        signatures (incremental update).

    **References:**
    This implementation adheres to the standards defined in:

    * `Adobe PDF Reference (v1.7) <https://ia601001.us.archive.org/1/items/pdf1.7/pdf_reference_1-7.pdf>`_
        (For the general structure of the PDF document).
    * `Digital Signatures in a PDF <https://www.adobe.com/devnet-docs/acrobatetk/tools/DigSig/Acrobat_DigitalSignatures_in_PDF.pdf>`_
        (For the specific structure of the signature dictionary).

    :param pdf_raw: The raw bytes of the original PDF file.
    :type pdf_raw: bytes
    :param company: The Odoo company record containing the signing certificate/key.
    :type company: ResCompany or None
    :param signing_time: Optional datetime to use as the signing timestamp.
                         Defaults to ``datetime.now()``.
    :type signing_time: datetime or None
    """

    def __init__(self, pdf_raw: bytes, company: ResCompany | None = None, signing_time=None) -> None:
        self.pdf_raw = pdf_raw
        self.pdf_reader = PdfFileReader(io.BytesIO(pdf_raw), strict=False)
        self.company = company
        self.signing_time = signing_time or datetime.datetime.now(datetime.timezone.utc)

    def pdf_contains_signature(self) -> bool:
        """ Checks if the PDF document contains at least one actively applied digital signature.

        :return: True if at least one applied signature exists, False otherwise.
        :rtype: bool
        """
        form_fields = self.pdf_reader.get_fields()
        if form_fields:
            for field in form_fields:
                field_dict = form_fields[field]
                if field_dict.get("/FT") == "/Sig" and "/V" in field_dict:
                    return True

        return False

    def sign_pdf(self, sig_overlay_pdf: PdfFileReader = None, field_name: str = "Odoo Signature") -> bytes | None:
        """ Inject a cryptographic digital signature into the PDF document.

        Prepares the document by creating a signature field and appending an
        optional visual representation, then finalizes the file with an
        incremental update and cryptographic injection.

        :param sig_overlay_pdf: The parsed PDF widget to overlay as the signature appearance.
        :type sig_overlay_pdf: PyPDF2.PdfFileReader | None
        :param field_name: The unique dictionary name for the signature field.
        :type field_name: str
        :return: The signed PDF data, or None if cryptographic keys/dependencies are missing.
        :rtype: bytes | None
        """
        if not self.company or not load_pem_x509_certificates:
            return

        incremented_objects = {}

        # 1. Normalize PDF annotations in case it wasn't signed before
        self._normalize_unsigned_pdf_annotations()

        # 2. Prepare the Signature Field Structure
        self._setup_form(self.pdf_reader, field_name, incremented_objects, sig_overlay_pdf)

        # 3. Write the Incremental Updated PDF (with empty signature placeholders)
        pdf_merger = IncrementalPdfMerge(self.pdf_raw)
        xref = pdf_merger._write_incremented_pdf(self.pdf_reader, incremented_objects)

        # 4. Get the signature object offset
        sig_obj_start = None
        for obj_key, obj_data in incremented_objects.items():
            if "/Type" in obj_data and obj_data["/Type"] == "/Sig":
                sig_obj_start = xref[obj_key]
                break

        # 5. Sign the Document (fill the signature placeholders)
        final_output = pdf_merger.get_output_stream_value()
        signed_pdf_bytes = self._perform_signature(final_output, sig_obj_start)

        return signed_pdf_bytes

    def _normalize_unsigned_pdf_annotations(self):
        """ Prepares an unsigned PDF for sequential digital signing by normalizing annotations.

        If the document is already signed, this method safely exits to preserve the
        existing cryptographic hashes. For unsigned documents, it runs a discrete
        incremental update to force all page ``/Annots`` arrays into indirect objects.

        This structural normalization ensures that when subsequent signatures are
        applied, only the isolated annotation arrays are modified in the XRef table.
        """
        if not self.pdf_contains_signature():
            pdf_merger = IncrementalPdfMerge(self.pdf_raw)
            pdf_merger.normalize_pages_annotations_to_indirect()
            self.pdf_raw = pdf_merger.get_output_stream_value()
            self.pdf_reader = PdfFileReader(io.BytesIO(self.pdf_raw), strict=False)

    def _load_key_and_certificates(self) -> tuple[PrivateKeyTypes | None, Certificate | None, list[Certificate] | None]:
        """ Retrieves and deserializes the private key and certificate from the company record.

        :return: A tuple ``(private_key, certificate)``. Returns ``(None, None)`` if
                 the company has no valid certificate configured.
        :rtype: tuple
        """
        certificate = self.company.signing_certificate_id if "signing_certificate_id" in self.company._fields else None
        if not (certificate and certificate.pem_certificate and certificate.private_key_id and certificate.private_key_id.content):
            return None, None, None

        cert_bytes = certificate.pem_certificate.content
        private_key_bytes = certificate.private_key_id.content.content
        all_certs = load_pem_x509_certificates(cert_bytes)

        leaf_cert = all_certs[0]
        cert_chain = all_certs[1:]
        private_key = load_pem_private_key(private_key_bytes, None)

        return private_key, leaf_cert, cert_chain

    def _setup_form(
            self,
            pdf_reader: PdfFileReader,
            field_name: str,
            incremented_objects: dict[tuple[int, int], Any],
            sig_overlay_pdf: PdfFileReader = None,
    ) -> None:
        """ Configure the PDF ``/AcroForm`` and create the required Signature Field dictionaries.

        This method mutates the PDF object graph by injecting:
        1. **AcroForm Dictionary:** Enables forms and sets ``SigFlags`` to 3 (Signatures Exist | Append Only).
        2. **Signature Field:** The core field definition (e.g., ``/FT /Sig``).
        3. **Visual Appearance:** If provided, embeds the ``sig_overlay_pdf`` as a Form XObject widget.
        4. **Signature Value:** A placeholder dictionary (``/Contents`` and ``/ByteRange``) ready for cryptographic injection.

        :param pdf_reader: The reader object holding the current document state.
        :type pdf_reader: PdfFileReader
        :param field_name: The internal name identifier for the signature field.
        :type field_name: str
        :param incremented_objects: Mapping of modified ``(object_id, generation)`` tuples for the incremental save.
        :type incremented_objects: dict[tuple[int, int], Any]
        :param sig_overlay_pdf: An optional pre-rendered PDF containing the visual widget overlay.
        :type sig_overlay_pdf: PdfFileReader | None
        """
        indirect_obj_wrapper = IndirectObjectsWrapper()  # A temporary Wrapper for new objects, useful for the indirect traverse
        catalog = pdf_reader.trailer[TK.ROOT]

        # 1. Setup the AcroForm
        acro_form_originally_exist = False
        if CD.ACRO_FORM not in catalog:
            acro_form = DictionaryObject()
            acro_form.update({
                NameObject(IF.SigFlags): NumberObject(3)
            })
            catalog[NameObject(CD.ACRO_FORM)] = indirect_obj_wrapper.add_object(acro_form)
        else:
            acro_form_originally_exist = True
            acro_form = catalog[CD.ACRO_FORM].get_object()
            # Update flags: Allow Append Mode (Bit 2) | Signatures Exist (Bit 1) = 3
            if IF.SigFlags not in acro_form:
                acro_form[NameObject(IF.SigFlags)] = NumberObject(3)
            else:
                current_flags = acro_form[IF.SigFlags]
                acro_form[NameObject(IF.SigFlags)] = NumberObject(int(current_flags) | 3)

        # 2. Define the signature annotation dictionary
        # We create a Widget Annotation that acts as the signature field.
        # Flags=132 (Print + Locked): Visible when printed, cannot be deleted by user.
        page = pdf_reader.pages[0]
        signature_annotation = DictionaryObject()
        signature_annotation.update({
            NameObject("/FT"): NameObject("/Sig"),  # Field Type: Signature
            NameObject("/T"): create_string_object(field_name),
            NameObject("/Type"): NameObject("/Annot"),  # Object Type: Annotation
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/F"): NumberObject(132),  # Flags: Print | Locked
            NameObject("/P"): page.indirect_reference,
        })

        # 3. Construct the visual appearance widget (optional)
        signature_overlay = None
        content_stream = None

        if sig_overlay_pdf:
            signature_overlay = sig_overlay_pdf.pages[0]
            content_stream = signature_overlay.get_contents()

        if content_stream is not None:
            # Extract the font dictionaries and formatting from the overlay
            signature_resources = signature_overlay.get(PG.RESOURCES, DictionaryObject())

            # Determine the exact dimensions of the signature block
            calc_width = float(abs(signature_overlay.mediabox.width))
            calc_height = float(abs(signature_overlay.mediabox.height))

            # Calculate absolute coordinates on the first page (Top-Right placement)
            origin = page.mediabox.upper_right
            margin = 20

            x2 = int(float(origin[0]) - margin)
            y2 = int(float(origin[1]) - margin)
            x1 = int(x2 - calc_width)
            y1 = int(y2 - calc_height)

            rect = [x1, y1, x2, y2]

            # Build the Form XObject appearance stream dictionary
            # The /BBox uses local coordinates starting at (0,0) for the internal drawing
            signature_appearance_stream = StreamObject()
            signature_appearance_stream.update({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Form"),
                NameObject("/BBox"): ArrayObject([
                    NumberObject(0), NumberObject(0),
                    NumberObject(calc_width), NumberObject(calc_height)
                ]),
                NameObject("/Matrix"): ArrayObject([
                    NumberObject(1), NumberObject(0),
                    NumberObject(0), NumberObject(1),
                    NumberObject(0), NumberObject(0)
                ]),
                NameObject("/Resources"): signature_resources
            })

            # Inject the raw, drawing operations
            signature_appearance_stream._data = content_stream.get_data()

            # Wrap the XObject in an Appearance Dictionary (/AP) under the Normal (/N) state
            signature_appearance = DictionaryObject()
            signature_appearance.update({
                NameObject("/N"): signature_appearance_stream
            })

            # Bind the calculated position (/Rect) and the appearance (/AP) to the Annotation
            signature_annotation.update({
                NameObject("/Rect"): ArrayObject([NumberObject(x) for x in rect]),
                NameObject("/AP"): signature_appearance
            })
        else:
            # Invisible signature (Zero-width rect)
            signature_annotation.update({
                NameObject("/Rect"): ArrayObject([NumberObject(0), NumberObject(0), NumberObject(0), NumberObject(0)])
            })

        # 4. Prepare the signature object placeholders
        # /Contents: A large hex string (0-padded) to hold the CMS signature later.
        # /ByteRange: A placeholder array [0, 9999999999, 9999999999, 9999999999] to hold offsets later.
        # Reserve 60 bytes for ByteRange (enough for four 10-digit integers).
        byte_range_placeholder = ArrayObject([
            NumberObject(0),
            NumberObject(9999999999),
            NumberObject(9999999999),
            NumberObject(9999999999)
        ])

        signature_object = DictionaryObject()
        signature_object.update({
            NameObject("/Type"): NameObject("/Sig"),
            NameObject("/Contents"): ByteStringObject(b"\0" * 8192),
            NameObject("/ByteRange"): byte_range_placeholder,
            NameObject("/Filter"): NameObject("/Adobe.PPKLite"),
            NameObject("/SubFilter"): NameObject("/adbe.pkcs7.detached"),
            NameObject("/M"): create_string_object(self.signing_time.strftime("D:%Y%m%d%H%M%SZ")),
        })

        # Register objects with the temporary wrapper to get references
        signature_annotation_ref = indirect_obj_wrapper.add_object(signature_annotation)
        signature_object_ref = indirect_obj_wrapper.add_object(signature_object)

        # Link signature value dict to the field dict
        signature_annotation.update({
            NameObject("/V"): signature_object_ref
        })

        # 5. Register the signature annotation in the AcroForm fields, and the page annotations

        # Add to /AcroForm /Fields
        try:
            raw_fields = acro_form.raw_get("/Fields")
        except KeyError:
            raw_fields = None
        if raw_fields and isinstance(raw_fields, IndirectObject):
            fields_array = raw_fields.get_object()
            fields_array.append(signature_annotation_ref)
            raw_id = raw_fields.idnum
            raw_gen = raw_fields.generation
            if (raw_id, raw_gen) not in incremented_objects:
                incremented_objects[raw_id, raw_gen] = fields_array
            IncrementalPdfMerge.update_cached_indirect_object(pdf_reader, raw_gen, raw_id, fields_array)
        else:
            if raw_fields is None:
                raw_fields = ArrayObject()
            raw_fields.append(signature_annotation_ref)
            acro_form[NameObject("/Fields")] = raw_fields

        # Add to Page /Annots
        try:
            raw_annots = page.raw_get(PG.ANNOTS)
        except KeyError:
            raw_annots = None
        if raw_annots and isinstance(raw_annots, IndirectObject):
            annots_array = raw_annots.get_object()
            annots_array.append(signature_annotation_ref)
            raw_id = raw_annots.idnum
            raw_gen = raw_annots.generation
            if (raw_id, raw_gen) not in incremented_objects:
                incremented_objects[raw_id, raw_gen] = annots_array
            IncrementalPdfMerge.update_cached_indirect_object(pdf_reader, raw_gen, raw_id, annots_array)
        else:
            if raw_annots is None:
                raw_annots = ArrayObject()
            raw_annots.append(signature_annotation_ref)
            page[NameObject(PG.ANNOTS)] = raw_annots

            page_ref_id = page.indirect_reference.idnum
            page_ref_gen = page.indirect_reference.generation
            if (page_ref_id, page_ref_gen) not in incremented_objects:
                incremented_objects[page_ref_id, page_ref_gen] = page
            IncrementalPdfMerge.update_cached_indirect_object(pdf_reader, page_ref_gen, page_ref_id, page)

        root_entry = pdf_reader.trailer.raw_get(TK.ROOT)
        if isinstance(root_entry, IndirectObject):
            # If Root is indirect, we must explicitly track it for the incremental update
            incremented_objects[root_entry.idnum, root_entry.generation] = catalog
            IncrementalPdfMerge.update_cached_indirect_object(pdf_reader, root_entry.generation, root_entry.idnum, catalog)

        acro_ref = catalog.raw_get(CD.ACRO_FORM)
        if acro_form_originally_exist and isinstance(acro_ref, IndirectObject):
            incremented_objects[acro_ref.idnum, acro_ref.generation] = acro_form
            IncrementalPdfMerge.update_cached_indirect_object(pdf_reader, acro_ref.generation, acro_ref.idnum, acro_form)

    def _get_cms_object(self, digest: bytes) -> cms.ContentInfo | None:
        """ Wraps the document hash in a Cryptographic Message Syntax (CMS) structure.

        This conforms to **RFC 5652**. It creates a detached signature (ContentInfo)
        containing the signer's leaf_cert, the signing time, and the signed digest.

        RFC: https://datatracker.ietf.org/doc/html/rfc5652

        :param digest: The SHA-256 hash of the relevant PDF byte ranges.
        :type digest: bytes
        :return: A CMS object populated with the signature data.
        :rtype: cms.ContentInfo or None
        """
        try:
            private_key, leaf_cert, cert_chain = self._load_key_and_certificates()
        except ValueError as e:
            _logger.warning("Skipping PDF signature: Unable to load PEM file. Reason: %s", e)
            return None

        if private_key is None or leaf_cert is None:
            return None

        cert = x509.Certificate.load(
            leaf_cert.public_bytes(encoding=Encoding.DER)
        )
        all_certificates = [cert]
        if cert_chain:
            for intermediate_cert in cert_chain:
                all_certificates.append(
                    x509.Certificate.load(
                        intermediate_cert.public_bytes(encoding=Encoding.DER)
                    )
                )

        encap_content_info = {
            'content_type': 'data',
            'content': None
        }

        # Define CMS attributes (ContentType, SigningTime, AlgorithmProtection, MessageDigest)
        attrs = cms.CMSAttributes([
            cms.CMSAttribute({
                'type': 'content_type',
                'values': ['data']
            }),
            cms.CMSAttribute({
                'type': 'signing_time',
                'values': [cms.Time({'utc_time': core.UTCTime(self.signing_time)})]
            }),
            cms.CMSAttribute({
                'type': 'cms_algorithm_protection',
                'values': [
                        cms.CMSAlgorithmProtection(
                            {
                                'mac_algorithm': None,
                                'digest_algorithm': cms.DigestAlgorithm(
                                    {'algorithm': 'sha256', 'parameters': None}
                                ),
                                'signature_algorithm': cms.SignedDigestAlgorithm({
                                    'algorithm': 'sha256_rsa',
                                    'parameters': None
                                })
                            }
                        )
                ]
            }),
            cms.CMSAttribute({
                'type': 'message_digest',
                'values': [digest],
            }),
        ])

        # Sign the attributes
        signed_attrs = private_key.sign(
            attrs.dump(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Assemble SignerInfo
        signer_info = cms.SignerInfo({
            'version': "v1",
            'digest_algorithm': algos.DigestAlgorithm({'algorithm': 'sha256'}),
            'signature_algorithm': algos.SignedDigestAlgorithm({'algorithm': 'sha256_rsa'}),
            'signature': signed_attrs,
            'sid': cms.SignerIdentifier({
                'issuer_and_serial_number': cms.IssuerAndSerialNumber({
                    'issuer': cert.issuer,
                    'serial_number': cert.serial_number
                })
            }),
            'signed_attrs': attrs})

        # Encapsulate in SignedData
        signed_data = {
            'version': 'v1',
            'digest_algorithms': [algos.DigestAlgorithm({'algorithm': 'sha256'})],
            'encap_content_info': encap_content_info,
            'certificates': all_certificates,
            'signer_infos': [signer_info]
        }

        return cms.ContentInfo({
            'content_type': 'signed_data',
            'content': cms.SignedData(signed_data)
        })

    def _perform_signature(self, pdf_data: bytes, sig_obj_start: int) -> bytes | None:
        """ Injects the cryptographic signature into the reserved placeholders.

        This method performs the physical byte-level signing:
        1.  **Locate:** Finds the specific ``/ByteRange`` and ``/Contents`` placeholders
            belonging to the *last* signature object in the file.
        2.  **Calculate:** Determines the byte offsets to exclude the signature "hole"
            from the hash calculation.
        3.  **Hash & Sign:** Hashes the valid ranges, generates the CMS object.
        4.  **Inject:** Overwrites the placeholders in the byte stream with the
            calculated ByteRange and the hex-encoded CMS signature.

        :param pdf_data: The complete PDF file bytes containing the empty signature fields.
        :type pdf_data: bytes
        :param sig_obj_start: The absolute byte offset where the new signature dictionary
        begins within the ``pdf_data``.
        :type sig_obj_start: int
        :return: The final signed PDF bytes.
        :rtype: bytes
        :raises ValueError: If ``sig_obj_start`` is falsy (indicating no placeholder was
            found in the update), if the byte placeholders cannot be located within the
            stream, or if the generated CMS signature is too large for the reserved buffer.
        """
        pdf_buffer = bytearray(pdf_data)

        # Find the target signature object (last /Type /Sig in the file)
        if not sig_obj_start:
            raise ValueError("No signature placeholder found in the incremental update.")

        # Locate ByteRange and Contents by searching forward from the object start to find the specific keys belonging to them
        br_key_pos = pdf_buffer.find(b"/ByteRange", sig_obj_start)
        array_start = pdf_buffer.find(b"[", br_key_pos)
        array_end = pdf_buffer.find(b"]", array_start) + 1
        placeholder_len = array_end - array_start

        # Locate Contents hex string < ... >
        hex_start = pdf_buffer.find(b"<0000", sig_obj_start) + 1
        hex_end = pdf_buffer.find(b">", hex_start)  # Byte after hex data

        # Calculate the signature byte-range values
        # val1: Start of file (always 0)
        # val2: Length of first chunk (up to the opening '<')
        # val3: Offset where second chunk starts (after the closing '>')
        # val4: Length of the second chunk (from val3 to EOF)
        val1 = 0
        val2 = hex_start - 1  # The index of the '<'
        val3 = hex_end + 1  # The index after the '>'
        val4 = len(pdf_buffer) - val3

        # Update the byte-range placeholder and space pad it by transforming  "[0 999...]" into "[0 123 456 789     ]",
        # This keeps the total length IDENTICAL and valid.
        prefix = f"[{val1} {val2} {val3} ".encode('ascii')
        suffix = b"]"

        # Calculate how much room is left for the last number
        # Total Available - Prefix length - Suffix length
        available_len_for_val4 = placeholder_len - len(prefix) - len(suffix)

        if available_len_for_val4 < len(str(val4)):
            raise ValueError(f"Not enough space! Need {len(str(val4))}, have {available_len_for_val4}")

        # Format val4 with leading spaces
        s_val4 = str(val4).ljust(available_len_for_val4).encode('ascii')

        # Combine the new byte range
        new_range_str = prefix + s_val4 + suffix

        # Overwrite the buffer
        pdf_buffer[array_start:array_end] = new_range_str

        # We take every byte except the actual signature hex between hex_start-1 and hex_end+1
        data_to_hash = (
                pdf_buffer[val1: val1 + val2] +
                pdf_buffer[val3: val3 + val4]
        )
        digest = hashlib.sha256(data_to_hash).digest()

        # Generate and inject the CMS
        cms_content_info = self._get_cms_object(digest)
        if cms_content_info is None:
            return None

        signature_hex = cms_content_info.dump().hex().encode('ascii')

        max_hex_len = hex_end - hex_start
        if len(signature_hex) > max_hex_len:
            raise ValueError(f"CMS signature ({len(signature_hex)}) too large for hole ({max_hex_len})")

        # Fill the buffer with the signature, pad with '0'
        pdf_buffer[hex_start:hex_end] = signature_hex.ljust(max_hex_len, b"0")

        return bytes(pdf_buffer)
