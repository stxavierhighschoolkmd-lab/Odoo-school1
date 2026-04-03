import base64
import datetime
from importlib import metadata
import re
from contextlib import suppress

from cryptography import x509
from cryptography.x509.oid import ExtensionOID
from cryptography.x509.extensions import ExtensionNotFound
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import constant_time, serialization
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12, PublicFormat

from odoo import _, api, fields, models
from .key import STR_TO_HASH, _get_formatted_value
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import parse_version


class Certificate(models.Model):
    _name = 'certificate.certificate'
    _description = 'Certificate'
    _order = 'date_end DESC'
    _check_company_auto = True

    name = fields.Char(string='Name')
    content = fields.Binary(string='Certificate', readonly=False, required=True)
    pkcs12_password = fields.Char(string='Certificate Password', help='Password to decrypt the PKS file.')
    private_key_id = fields.Many2one(
        string='Private Key',
        comodel_name='certificate.key',
        check_company=True,
        domain=[('public', '=', False)],
        compute='_compute_private_key',
        store=True,
        readonly=False,
    )
    public_key_id = fields.Many2one(
        string='Public Key',
        comodel_name='certificate.key',
        check_company=True,
        domain=[('public', '=', True)],
        help="""Used to set a public key in case the one self-contained in the certificate is erroneus.
                When a public key is set this way, it will be used instead of the one in the certificate.
             """,
    )
    scope = fields.Selection(
        string="Certificate scope",
        selection=[
            ('general', 'General'),
        ],
    )
    content_format = fields.Selection(
        selection=[
            ('der', 'DER'),
            ('pem', 'PEM'),
            ('pkcs12', 'PKCS12'),
        ],
        string='Original certificate format',
        compute='_compute_pem_certificate',
        store=True,
    )
    pem_certificate = fields.Binary(
        string='Certificate in PEM format',
        compute='_compute_pem_certificate',
        store=True,
    )
    subject_common_name = fields.Char(
        string='Subject Name',
        compute='_compute_pem_certificate',
        store=True,
    )
    serial_number = fields.Char(
        string='Serial number',
        help='The serial number to add to electronic documents',
        compute='_compute_pem_certificate',
        store=True,
    )
    date_start = fields.Datetime(
        string='Available date',
        help='The date on which the certificate starts to be valid (UTC)',
        compute='_compute_pem_certificate',
        store=True,
    )
    date_end = fields.Datetime(
        string='Expiration date',
        help='The date on which the certificate expires (UTC)',
        compute='_compute_pem_certificate',
        store=True,
    )
    loading_error = fields.Text(string='Loading error', compute='_compute_pem_certificate', store=True)
    is_valid = fields.Boolean(string='Valid', compute='_compute_is_valid', search='_search_is_valid')
    active = fields.Boolean(name='Active', help='Set active to false to archive the certificate', default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='cascade',
    )
    country_code = fields.Char(related='company_id.country_code', depends=['company_id'])
    issuer_cert_id = fields.Many2one(
        comodel_name='certificate.certificate',
        string='Issuer Certificate',
        compute='_compute_issuer_cert_id',
    )

    @api.depends('pem_certificate', 'subject_common_name', 'company_id')
    def _compute_issuer_cert_id(self):
        self.issuer_cert_id = False

        valid_certs = self.filtered('pem_certificate')
        if not valid_certs:
            return

        cert_data = []
        issuer_cns = set()
        for certificate in valid_certs:
            try:
                raw_pem = base64.b64decode(certificate.with_context(bin_size=False).pem_certificate)
                cert = x509.load_pem_x509_certificate(raw_pem)
                if issuer_name_attrs := cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME):
                    issuer_cn = issuer_name_attrs[0].value
                    expected_ski = self._get_authority_key_identifier(cert)
                    cert_data.append({
                        'certificate': certificate,
                        'issuer_cn': issuer_cn,
                        'expected_ski': expected_ski,
                    })
                    issuer_cns.add(issuer_cn)
            except Exception:  # noqa: BLE001
                pass

        if not issuer_cns:
            return

        companies = valid_certs.mapped('company_id')
        potential_issuers = self.with_context(active_test=False).env['certificate.certificate'].search([
            *self.env['certificate.certificate']._check_company_domain(companies),
            ('subject_common_name', 'in', list(issuer_cns)),
            ('pem_certificate', '!=', False),
            ('id', 'not in', valid_certs.ids),
        ])

        issuers_by_cn = {}
        for issuer in potential_issuers:
            cn = issuer.subject_common_name
            if cn not in issuers_by_cn:
                issuers_by_cn[cn] = self.env['certificate.certificate']
            issuers_by_cn[cn] += issuer

        for data in cert_data:
            certificate = data['certificate']
            expected_ski = data['expected_ski']

            valid_candidates = issuers_by_cn.get(data['issuer_cn'], self.env['certificate.certificate']).filtered(
                lambda i: not i.company_id or i.company_id == certificate.company_id
            )

            for potential_issuer in valid_candidates:
                try:
                    parent_raw_pem = base64.b64decode(potential_issuer.with_context(bin_size=False).pem_certificate)
                    parent_cert = x509.load_pem_x509_certificate(parent_raw_pem)

                    if expected_ski:
                        ski = self._get_subject_key_identifier(parent_cert)
                        if ski == expected_ski:
                            certificate.issuer_cert_id = potential_issuer.id
                            break
                    else:
                        # Fallback to any of the candidates if extensions are missing
                        certificate.issuer_cert_id = potential_issuer.id
                        break
                except Exception:  # noqa: BLE001
                    pass

    @api.depends('pem_certificate')
    def _compute_private_key(self):
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'certificate.key'),
            ('res_field', '=', 'content'),
            ('res_id', 'in', self.ids)
        ])
        content_to_key_id = {(att.datas, att.company_id.id): att.res_id for att in attachments}

        for certificate in self:
            if not certificate.pem_certificate:
                certificate.private_key_id = None
                continue

            if certificate.private_key_id:
                continue

            content = certificate.with_context(bin_size=False).content
            key_password = certificate.pkcs12_password.encode('utf-8') if certificate.pkcs12_password else None
            key = None

            # Create the private key if using PKCS12 or PEM files and no private key is set
            if certificate.content_format == 'pkcs12':
                key, _cert, _additional_certs = pkcs12.load_key_and_certificates(base64.b64decode(content), key_password)
            elif certificate.content_format == 'pem':
                with suppress(ValueError, TypeError, UnsupportedAlgorithm):
                    key = serialization.load_pem_private_key(base64.b64decode(content), password=key_password)

            if key:
                pem_key = base64.b64encode(key.private_bytes(
                    encoding=Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                key_id = content_to_key_id.get((pem_key, certificate.company_id.id))
                if not key_id:
                    key_id = self.env['certificate.key'].create({
                        'name': (certificate.subject_common_name or certificate.name or "") + ".key",
                        'content': pem_key,
                        'company_id': certificate.company_id.id,
                    })
                certificate.private_key_id = key_id

    @api.depends('content', 'pkcs12_password')
    def _compute_pem_certificate(self):
        for certificate in self:
            content = certificate.with_context(bin_size=False).content

            if not content:
                certificate.pem_certificate = None
                certificate.subject_common_name = None
                certificate.content_format = None
                certificate.date_start = None
                certificate.date_end = None
                certificate.serial_number = None
                certificate.loading_error = ""

            else:
                pkcs12_password = certificate.pkcs12_password.encode('utf-8') if certificate.pkcs12_password else None
                leaf_pem, _, certificate.content_format = self._parse_certificate_content(content, pkcs12_password)

                if not leaf_pem:
                    certificate.pem_certificate = None
                    certificate.subject_common_name = None
                    certificate.content_format = None
                    certificate.date_start = None
                    certificate.date_end = None
                    certificate.serial_number = None

                    if not certificate.pkcs12_password:
                        certificate.loading_error = ""
                    else:
                        certificate.loading_error = _(
                            "This certificate could not be loaded. Either the content or the password is erroneous.")
                    continue

                cert = x509.load_pem_x509_certificate(leaf_pem)

                try:
                    common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                    certificate.subject_common_name = common_name[0].value if common_name else ""
                except ValueError:
                    certificate.subject_common_name = None

                certificate.loading_error = ""

                # Extract certificate data
                certificate.pem_certificate = base64.b64encode(leaf_pem)
                certificate.serial_number = cert.serial_number
                if parse_version(metadata.version('cryptography')) < parse_version('42.0.0'):
                    certificate.date_start = cert.not_valid_before
                    certificate.date_end = cert.not_valid_after
                else:
                    certificate.date_start = cert.not_valid_before_utc.replace(tzinfo=None)
                    certificate.date_end = cert.not_valid_after_utc.replace(tzinfo=None)

    @api.depends('date_start', 'date_end', 'loading_error')
    def _compute_is_valid(self):
        # Certificate dates are UTC timezoned
        # https://cryptography.io/en/latest/x509/reference/#cryptography.x509.Certificate.not_valid_after
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        for certificate in self:
            if not certificate.date_start or not certificate.date_end or certificate.loading_error:
                certificate.is_valid = False
            else:
                date_start = certificate.date_start.replace(tzinfo=datetime.timezone.utc)
                date_end = certificate.date_end.replace(tzinfo=datetime.timezone.utc)
                certificate.is_valid = date_start <= utc_now <= date_end

    def _search_is_valid(self, operator, value):
        if operator not in ['=', '!='] or not isinstance(value, bool):
            raise NotImplementedError("Operation not supported, only '=' and '!=' are allowed.")
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('pem_certificate', '!=', False),
                ('date_start', '<=', utc_now),
                ('date_end', '>=', utc_now),
                ('loading_error', '=', '')
            ]
        else:
            return expression.OR([
                [('pem_certificate', '=', False)],
                [('date_start', '=', False)],
                [('date_end', '=', False)],
                [('date_start', '>', utc_now)],
                [('date_end', '<', utc_now)],
                [('loading_error', '!=', '')],
            ])

    @api.constrains('pem_certificate', 'private_key_id', 'public_key_id')
    def _constrains_certificate_key_compatibility(self):
        for certificate in self:
            pem_certificate = certificate.with_context(bin_size=False).pem_certificate
            if pem_certificate:
                cert = x509.load_pem_x509_certificate(base64.b64decode(pem_certificate))
                cert_public_key_bytes = cert.public_key().public_bytes(
                    encoding=Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )

                if certificate.private_key_id:
                    if certificate.private_key_id.loading_error:
                        raise ValidationError(certificate.private_key_id.loading_error)
                    pkey_public_key_bytes = base64.b64decode(
                        certificate.private_key_id._get_public_key_bytes(encoding='pem')
                    )
                    if not constant_time.bytes_eq(pkey_public_key_bytes, cert_public_key_bytes):
                        raise ValidationError(_("The certificate and private key are not compatible."))

                if certificate.public_key_id:
                    if certificate.public_key_id.loading_error:
                        raise ValidationError(certificate.public_key_id.loading_error)
                    pkey_public_key_bytes = base64.b64decode(
                        certificate.public_key_id._get_public_key_bytes(encoding='pem')
                    )
                    if not constant_time.bytes_eq(pkey_public_key_bytes, cert_public_key_bytes):
                        raise ValidationError(_("The certificate and public key are not compatible."))

    @api.constrains('content', 'pem_certificate')
    def _constrains_certificate_loaded(self):
        for certificate in self:
            if certificate.content and not certificate.pem_certificate:
                raise ValidationError(
                    certificate.loading_error
                    or _("This certificate could not be loaded. Please provide the certificate password.")
                )

    # -------------------------------------------------------
    # Content Extraction Logic
    # -------------------------------------------------------
    @api.model
    def _get_subject_key_identifier(self, x509_cert):
        """ Helper to safely extract the Subject Key Identifier (SKI) """
        try:
            return x509_cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER).value.digest
        except ExtensionNotFound:
            return None

    @api.model
    def _get_authority_key_identifier(self, x509_cert):
        """ Helper to safely extract the Authority Key Identifier (AKI) """
        try:
            return x509_cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_KEY_IDENTIFIER).value.key_identifier
        except ExtensionNotFound:
            return None

    @api.model
    def _parse_pem_certificate_bundle(self, decoded_content, password=None):
        pattern = (
            rb'('
            rb'-----BEGIN CERTIFICATE-----'
            rb'.*?'
            rb'-----END CERTIFICATE-----'
            rb')'
        )
        cert_blocks = re.findall(pattern, decoded_content, flags=re.DOTALL)
        certs = [x509.load_pem_x509_certificate(block) for block in cert_blocks]

        private_key = None
        with suppress(ValueError, TypeError, UnsupportedAlgorithm):
            # Suppress errors because the bundle might only contain public certificates
            # (like a CA bundle) and lack a private key, or the password could be missing/incorrect.
            private_key = serialization.load_pem_private_key(decoded_content, password=password)

        leaf_cert = None
        additional_certs = []
        if private_key:
            target_pub_bytes = private_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
            for cert in certs:
                curr_pub_bytes = cert.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
                if curr_pub_bytes == target_pub_bytes:
                    leaf_cert = cert
                else:
                    additional_certs.append(cert)

        if not leaf_cert and certs:
            # Fallback to TLS standard if a key didn't match any cert
            leaf_cert = certs[0]
            additional_certs = certs[1:]

        leaf_pem, *additional_pems = [c.public_bytes(Encoding.PEM) if c else None for c in [leaf_cert, *additional_certs]]

        return leaf_pem, additional_pems

    @api.model
    def _parse_certificate_content(self, content, password=None):
        content = base64.b64decode(content)
        leaf_pem = None
        leaf_cert = None
        additional_pems = []
        additional_certs = []
        content_format = None

        # Try to load the certificate in different format starting with DER then PKCS12 and
        # finally PEM. If none succeeded, we report an error.
        try:
            leaf_cert = x509.load_der_x509_certificate(content)
            content_format = 'der'
        except ValueError:
            pass
        if not leaf_cert:
            try:
                _key, leaf_cert, additional_certs = pkcs12.load_key_and_certificates(content, password)
                content_format = 'pkcs12'
            except ValueError:
                pass
        if not leaf_cert:
            try:
                leaf_pem, additional_pems = self._parse_pem_certificate_bundle(content, password)
                content_format = 'pem'
            except ValueError:
                pass

        if content_format and content_format != 'pem':
            # `_parse_pem_certificate_bundle` is already returning the certs as PEM bytes
            leaf_pem, *additional_pems = [c.public_bytes(Encoding.PEM) for c in [leaf_cert, *additional_certs]]

        return leaf_pem, additional_pems, content_format

    @api.model
    def _extract_and_filter_chain(self, content_bytes, password=None):
        """ Parses a bundle and returns only the certificates forming the leaf's chain """
        leaf_pem, additional_pems, _ = self._parse_certificate_content(content_bytes, password)
        if not leaf_pem:
            return []

        ski_cert_map = {}
        for pem in additional_pems:
            cert = x509.load_pem_x509_certificate(pem)
            if ski := self._get_subject_key_identifier(cert):
                ski_cert_map[ski] = cert

        leaf_cert = x509.load_pem_x509_certificate(leaf_pem)
        certs_chain = [leaf_cert]
        current_cert = leaf_cert

        # Traverse upward: Current AKI -> Parent SKI
        while (
            (aki := self._get_authority_key_identifier(current_cert))
            and (parent_cert := ski_cert_map.get(aki))
            and parent_cert not in certs_chain  # Prevents infinite loops (e.g., self-signed roots)
        ):
            certs_chain.append(parent_cert)
            current_cert = parent_cert

        return [c.public_bytes(Encoding.PEM) for c in certs_chain]

    # -------------------------------------------------------
    # ORM Overrides for Auto-CA Creation
    # -------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Skip chain extraction for auto-generated CA records to prevent infinite recursion
        if self.env.context.get('_is_ca_import'):
            return records

        for record in records:
            if record.content and not record.loading_error:
                record._process_chain_creation()

        return records

    def write(self, vals):
        res = super().write(vals)

        # Skip chain extraction for auto-generated CA records to prevent infinite recursion
        if self.env.context.get('_is_ca_import'):
            return res

        if 'content' in vals or 'pkcs12_password' in vals:
            for record in self:
                if record.content and not record.loading_error:
                    record._process_chain_creation()

        return res

    def _process_chain_creation(self):
        """ Extracts chain from certificate and creates missing CAs in database """
        self.ensure_one()

        content_bytes = self.with_context(bin_size=False).content
        password = self.pkcs12_password.encode('utf-8') if self.pkcs12_password else None

        _, *ca_pems = self._extract_and_filter_chain(content_bytes, password)  # Skip the first one (the leaf, which is already saved)
        if not ca_pems:
            return  # Only the leaf, or parsing failed

        ca_data_list = []
        serial_numbers = []
        for ca_pem in ca_pems:
            ca_cert = x509.load_pem_x509_certificate(ca_pem)
            serial_str = str(ca_cert.serial_number)
            cn = ""
            with suppress(ValueError, IndexError):
                cn = ca_cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value

            ca_data_list.append({
                'serial_str': serial_str,
                'cn': cn,
                'pem_bytes': ca_pem,
            })
            serial_numbers.append(serial_str)

        existing_cas = self.with_context(active_test=False).search([
            *self.env['certificate.certificate']._check_company_domain(self.company_id),
            ('serial_number', 'in', serial_numbers),
        ])

        existing_ca_keys = {
            (ca.serial_number, ca.subject_common_name)
            for ca in existing_cas
        }

        ca_create_vals = []
        for ca_data in ca_data_list:
            key = (ca_data['serial_str'], ca_data['cn'])

            # If the certificate doesn't exist in the database, then we creat it
            if key not in existing_ca_keys:
                ca_create_vals.append({
                    'name': f"{ca_data['cn']} (CA)",
                    'content': base64.b64encode(ca_data['pem_bytes']),
                    'active': False,  # Hide from standard views
                    'company_id': self.company_id.id,
                })
                # Add to the set so we don't create duplicates if the bundle contains the same CA twice
                existing_ca_keys.add(key)

        if ca_create_vals:
            self.with_context(_is_ca_import=True).create(ca_create_vals)

    # -------------------------------------------------------
    #                   Business Methods                    #
    # -------------------------------------------------------

    def _get_der_certificate_bytes(self, formatting='encodebytes'):
        ''' Get the DER bytes of the certificate.

        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: The formatted DER bytes of the certificate
        :rtype: bytes
        '''
        self.ensure_one()
        cert = x509.load_pem_x509_certificate(base64.b64decode(self.with_context(bin_size=False).pem_certificate))
        return _get_formatted_value(cert.public_bytes(serialization.Encoding.DER), formatting=formatting)

    def _get_fingerprint_bytes(self, hashing_algorithm='sha256', formatting='encodebytes'):
        ''' Get the fingerprint bytes of the certificate.

        :param optional,default='sha256' hashing_algorithm: The digest algorithm to use. Currently, only 'sha1' and 'sha256' are available.
        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: The formatted fingerprint bytes of the certificate
        :rtype: bytes
        '''
        self.ensure_one()
        cert = x509.load_pem_x509_certificate(base64.b64decode(self.with_context(bin_size=False).pem_certificate))
        if hashing_algorithm not in STR_TO_HASH:
            raise UserError(f"Unsupported hashing algorithm '{hashing_algorithm}'. Currently supported: sha1 and sha256.")
        return _get_formatted_value(cert.fingerprint(STR_TO_HASH[hashing_algorithm]), formatting=formatting)

    def _get_signature_bytes(self, formatting='encodebytes'):
        ''' Get the signature bytes of the certificate.

        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: The formatted signature bytes of the certificate
        :rtype: bytes
        '''
        self.ensure_one()
        cert = x509.load_pem_x509_certificate(base64.b64decode(self.with_context(bin_size=False).pem_certificate))
        return _get_formatted_value(cert.signature, formatting=formatting)

    def _get_public_key_numbers_bytes(self, formatting='encodebytes'):
        ''' Get the certificate public key's public numbers bytes.

        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: A tuple containing the formatted public number bytes of the certificate's public key

        :rtype: tuple(bytes,bytes)
        '''
        self.ensure_one()
        if self.public_key_id or self.private_key_id:
            return (self.public_key_id or self.private_key_id)._get_public_key_numbers_bytes(formatting=formatting)

        # When no keys are set to the certificate, use the self-contained public key from the content
        return self.env['certificate.key']._numbers_public_key_bytes_with_key(
            self._get_public_key_bytes(encoding='pem'),
            formatting=formatting,
        )

    def _get_public_key_bytes(self, encoding='der', formatting='encodebytes'):
        ''' Get the certificate's public key bytes.

        :param optional,default='der' encoding: The formatting of the returned bytes
            - 'der' returns DER public key bytes
            - other returns PEM public key bytes
        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: The formatted certificate public key bytes in the corresponding format
        :rtype: bytes
        '''
        self.ensure_one()
        if self.public_key_id or self.private_key_id:
            return (self.public_key_id or self.private_key_id)._get_public_key_bytes(encoding=encoding, formatting=formatting)

        # When no keys are set to the certificate, use the self-contained public key from the content
        try:
            cert = x509.load_pem_x509_certificate(base64.b64decode(self.with_context(bin_size=False).pem_certificate))
            public_key = cert.public_key()
        except ValueError:
            raise UserError(_("The public key from the certificate could not be loaded."))

        encoding = serialization.Encoding.DER if encoding == 'der' else serialization.Encoding.PEM
        return _get_formatted_value(
            public_key.public_bytes(
                encoding=encoding,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ),
            formatting=formatting,
        )

    def _sign(self, message, hashing_algorithm='sha256', formatting='encodebytes'):
        ''' Compute and return the message's signature.

        :param str|bytes message: The message to sign
        :param optional,default='sha256' hashing_algorithm: The digest algorithm to use. Currently, only 'sha1' and 'sha256' are available.
        :param optional,default='encodebytes' formatting: The formatting of the returned bytes
            - 'encodebytes' returns a base64-encoded block of 76 characters lines
            - 'base64' returns the raw base64-encoded data
            - other returns non-encoded data
        :return: The formatted signature bytes of the message
        :rtype: bytes
        '''
        self.ensure_one()

        if not self.is_valid:
            raise UserError(self.loading_error or _("This certificate is not valid, its validity has expired."))
        if not self.private_key_id:
            raise UserError(_("No private key linked to the certificate, it is required to sign documents."))

        return self.private_key_id._sign(message, hashing_algorithm=hashing_algorithm, formatting=formatting)

    def _get_certificate_chain(self):
        """
        Retrieves the full certificate chain as a recordset, starting from the current
        certificate and walking up the issuer_cert_id links.

        :return: A recordset of certificate.certificate objects ordered from Leaf to Root.
        """
        self.ensure_one()

        chain = self
        while (
                (current_cert := chain[-1].issuer_cert_id)
                and current_cert not in chain
        ):
            chain += current_cert

        return chain
