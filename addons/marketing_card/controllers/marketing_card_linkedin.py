import werkzeug
from urllib.parse import quote

from odoo.http import Controller, request, route
from odoo.exceptions import UserError

from odoo.addons.marketing_card.utils.linkedin_api import LinkedInAPI


class MarketingCardLinkedinController(Controller):
    _LINKEDIN_SHARE_CALLBACK_PATH = '/cards/share/linkedin/callback'

    @route(['/cards/<model("card.card"):card>/share/linkedin'], type='http', auth='public', website=True, sitemap=False)
    def linkedin_share_start(self, card, **kwargs):
        """Initiate LinkedIn OAuth flow for the visitor."""
        try:
            url = LinkedInAPI(self.env).get_authorization_url(
                redirect_uri=self._get_linkedin_card_share_redirect_uri(),
                state=card.id, scope='w_member_social openid profile',
            )
        except UserError:
            # if there's an error we can just let people share "normally", using opengraph
            url = f'https://www.linkedin.com/sharing/share-offsite/?url={quote(card._get_redirect_url())}'

        return request.redirect(url, local=False)

    @route([_LINKEDIN_SHARE_CALLBACK_PATH], type='http', auth='public', website=True, sitemap=False)
    def linkedin_share_callback(self, state, access_token=None, code=None, error=None, **kwargs):
        """Expect a response either from IAP or linkedin.

        :param string|None access_token: a linkedin access token provided by IAP
        :param string|None code: a linkedin authorization code provided by linkedin
        :param string state: expected to be the id of the card we're posting, provided by both
        :param string|None error: an error string, provided by both
        """
        card_id = int(state)  # state is a standard oauth parameter, for now we only store the card_id in it
        card = self.env['card.card'].browse(card_id).exists()
        if not card:
            return request.not_found()
        campaign_sudo = card.sudo().campaign_id
        render_values = {
            'campaign_sudo': campaign_sudo,
            'card': card,
            'linkedin_auth_state': 'missing'
        }

        if error or (not access_token and not code):
            return request.render('marketing_card.card_campaign_linkedin_share_composer', render_values | {
                'linkedin_auth_state': 'missing'
            })

        if not access_token:
            try:
                linkedin_api = LinkedInAPI(self.env)
                access_token = linkedin_api.fetch_access_token(code, self._get_linkedin_card_share_redirect_uri())
            except UserError:
                return request.render('marketing_card.card_campaign_linkedin_share_composer', render_values | {
                    'linkedin_auth_state': 'error'
                })

        linkedin_user_info = linkedin_api.get_user_info()
        http_response = request.render('marketing_card.card_campaign_linkedin_share_composer', render_values | {
            'linkedin_auth_state': 'success',
            'linkedin_user_fullname': linkedin_user_info.get('name'),
            'linkedin_user_picture_url': linkedin_user_info.get('picture'),
        })
        # The token is crucially not restricted to the app that requested it.
        # It is thus imperative that these settings be a strict a possible to prevent
        # other websites from sniffing it.
        http_response.set_cookie(
            'marketing_card_linkedin_personal_access_token', value=access_token,
            httponly=True, max_age=3600, path='/cards/', samesite="Strict", secure=True,
        )
        return http_response

    @route(['/cards/<model("card.card"):card>/share/linkedin/post'], type='http', methods=['POST'], auth='public', website=True, sitemap=False)
    def linkedin_post_with_access_token(self, card, text=''):
        api_token = request.cookies.get('marketing_card_linkedin_personal_access_token')
        if not api_token:
            request.make_response(status=401)

        linkedin_api = LinkedInAPI(self.env, access_token=api_token)
        linkedin_user_id = linkedin_api.get_user_info().get('sub')
        card_image_urn = linkedin_api.ugc_upload_image(card.image.content, owner_id=linkedin_user_id)
        post_response = linkedin_api.ugc_post_image(
            linkedin_user_id, text=text, image_urn=card_image_urn, image_title=card.display_name, image_description=card.display_name,
        )

        return request.redirect(f"https://www.linkedin.com/feed/update/{post_response.get('id')}", local=False)

    def _get_linkedin_card_share_redirect_uri(self):
        return werkzeug.urls.url_join(
            request.httprequest.url_root, MarketingCardLinkedinController._LINKEDIN_SHARE_CALLBACK_PATH,
        )
