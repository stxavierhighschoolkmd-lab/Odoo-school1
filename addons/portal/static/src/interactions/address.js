import { Interaction } from '@web/public/interaction';
import { registry } from '@web/core/registry';
import { rpc } from '@web/core/network/rpc';
import { redirect } from '@web/core/utils/urls';


export class CustomerAddress extends Interaction {
    // /my/address & /my/account
    static selector = '.o_customer_address_fill';
    dynamicContent = {
        // TODO VFE debounce other selection changes ?
        'select[name="state_id"]': { 't-on-change': this.onChangeState },
        'select[name="country_id"]': { 't-on-change': this.debounced(this.onChangeCountry, 500) },
        'select[name="city_id"]': { 't-on-change': this.onChangeCity },
        'input[name="zip"]': { 't-on-input': this.onChangeZip.bind(this) },
        '#save_address': { 't-on-click.prevent': this.locked(this.saveAddress, true) },
    };

    setup() {
        this.http = this.services['http'];
        this.addressForm = this.el.querySelector('form.address_autoformat');
        this.errorsDiv = this.el.querySelector('#errors');
        this.addressType = this.addressForm['address_type'].value;
        this.countryCode = this.addressForm.dataset.companyCountryCode;
        this.addressFields = ['street', 'zip', 'state_id', 'city', 'city_id'];

        // Required fields (defined server-side)
        this.requiredFields = this.addressForm.dataset.requiredFields.split(',');
        this.requiredFields.forEach((fieldName) => this._markRequired(fieldName, true));

        // Support for customizations and additional required fields
        this.alwaysRequiredFields = this.addressForm.required_fields.value.split(',');
        this.alwaysRequiredFields.forEach((fieldName) => this._markRequired(fieldName, true));

        this.elementCities = this.addressForm.city_id;
    }

    async willStart() {
        await this._onChangeCountry(true);
    }

    async onChangeCountry() {
        return this._onChangeCountry();
    }

    /**
     * Overridable hook.
     */
    async onChangeZip() {}

    async _onChangeCountry(init=false) {
        const countryId = parseInt(this.addressForm.country_id.value);
        if (!countryId) return;

        // TODO test and/or ask BOJE, what about autocomplete ?
        // Reset state and city inputs on country change.
        this.addressForm['state_id'].options.length = 1;
        this.addressForm['city_id'].options.length = 1;
        this.addressForm['city'].value = '';

        // TODO is_used_as_billing
        const data = await this.waitFor(rpc(
            `/my/address/country_info/${countryId}`,
            {address_type: this.addressType},
        ));

        this.addressForm.phone.placeholder = data.phone_code !== 0 ? `+${data.phone_code}` : '';

        // manage fields order / visibility
        if (data.address_fields) {
            // FIXME VFE, should support city_id too
            if (data.zip_before_city) {
                this._getInputDiv('zip').after(this._getInputDiv('city'));
            } else {
                this._getInputDiv('zip').before(this._getInputDiv('city'));
            }

            this.addressFields.forEach((fname) => {
                if (data.address_fields.includes(fname)) {
                    this._showInput(fname);
                    if (data.selection && fname in data.selection) {
                        // Configure the options for relational fields
                        this._setFieldChoices(
                            fname,
                            data.selection[fname],
                            data.required_fields.includes(fname),
                        );
                    }
                } else {
                    this._hideInput(fname);
                }
            });
        }

        let choices = [];
        if (this._getSelectedCountryEnforceCities()) {
            const cityInput = this.addressForm.city;
            cityInput.value = '';
            this._hideInput('city');
            this._showInput('city_id');
            choices = data.cities || [];
        } else {
            this._hideInput('city_id');
            this._showInput('city');
        }
        this._changeOption(this.elementCities, choices);

        // add requirement on now required fields
        data.required_fields.forEach((fieldName) => {
            // remove requirement on previously required fields
            if (
                !this.requiredFields.includes(fieldName)
                && !this.alwaysRequiredFields.includes(fieldName)
            ) {
                this._markRequired(fieldName, true);
            }
        });
        data.required_fields.forEach((fieldName) => {
            this._markRequired(fieldName, true);
        })

        return data;
    }

    async onChangeState() {
        let data = {
            'cities': [],
        }
        // TODO check if shown or hidden
        const stateId = parseInt(this.addressForm.state_id.value);
        if (stateId)  {
            data = await this.waitFor(rpc(`/my/address/state_info/${stateId}`, {}));
        }
        this._setFieldChoices('city_id', data.cities);

        return data;
    }

    //TODO VFE search city/cities based on provided zipcode ?

    /*
     * Auto-fill zip code according to chosen city
     */
    async onChangeCity() {
        const cityZipCode = this.addressForm.city_id.selectedOptions[0].dataset.zipcode;

        if (cityZipCode) {
            this.addressForm.zip.value = cityZipCode;
        }
    }

    _getInputDiv(name) {
        return this.addressForm[name].parentElement;
    }

    _getInputLabel(name) {
        const input = this.addressForm[name];
        return input?.parentElement.querySelector(`label[for='${input.id}']`);
    }

    _showInput(name) {
        // show parent div, containing label and input
        this.addressForm[name].parentElement.style.display = '';
    }

    _hideInput(name) {
        // show parent div, containing label and input
        this.addressForm[name].parentElement.style.display = 'none';
        // TODO reset field value or handle during form submission ?
    }

    _changeOption(selectElement, choices) {
        selectElement.options.length = 1;
        if (choices.length) {
            choices.forEach((choice) => {
                const option = new Option(choice.name, choice.id);
                Object.keys(choice).forEach((key) => {
                    if (!['name', 'id'].includes(key) && choice[key]) {
                        option.dataset[key] = choice[key];
                    }
                });
                selectElement.appendChild(option);
            });
        }
    }

    _getSelectedCountryEnforceCities() {
        const country = this.addressForm.country_id;
        return country.value ? country.selectedOptions[0].getAttribute('enforce-cities') : false;
    }

    _markRequired(name, required) {
        const input = this.addressForm[name];
        if (input) {
            input.required = required;
        }
        this._getInputLabel(name)?.classList.toggle('label-optional', !required);
    }

    _setFieldChoices(name, data_list) {
        const selection = this.addressForm[name];
        // empty existing options, only keep the first-choice placeholder.
        selection.options.length = 1;

        if (!data_list.length) {
            // this._hideInput(name);
            return
        }
        // create new options and append them to the select element
        data_list.forEach((choice) => {
            const option = new Option(choice.name, choice.id);
            Object.keys(choice).forEach((key) => {
                if (!['name', 'id'].includes(key) && choice[key]) {
                    option.dataset[key] = choice[key];
                }
            });
            selection.appendChild(option);
        });
        this._showInput(name);
    }

    /**
     * Disable the button, submit the form and add a spinner while the submission is ongoing.
     *
     * @param {Event} ev
     */
    async saveAddress(ev) {
        ev.preventDefault();  // avoid potential redirect if href set on link
        if (!this.addressForm.reportValidity()) return;

        const result = await this.waitFor(this.http.post(
            this.addressForm.dataset.submitUrl,
            new FormData(this.addressForm),
        ))
        if (result.redirectUrl) {
            redirect(result.redirectUrl);
        } else {
            // Highlight missing/invalid form values
            this.el.querySelectorAll('.is-invalid').forEach(element => {
                if (!result.invalid_fields.includes(element.name)) {
                    element.classList.remove('is-invalid');
                }
            })
            result.invalid_fields.forEach(
                fieldName => this.addressForm[fieldName].classList.add('is-invalid')
            );

            // Display the error messages
            // NOTE: setCustomValidity is not used as we would have to reset the error msg on
            // input update, which is not worth catching for the rare cases where the
            // server-side validation will catch validation issues (now that required inputs
            // are also handled client-side)
            const newErrors = result.messages.map(message => {
                const errorHeader = document.createElement('h5');
                errorHeader.classList.add('text-danger');
                errorHeader.appendChild(document.createTextNode(message));
                return errorHeader;
            });

            this.errorsDiv.replaceChildren(...newErrors);
        }
    }

    /**
     * Gets the selected country code.
     *
     * Used in overrides.
     */
    _getSelectedCountryCode() {
        const country = this.addressForm.country_id;
        return country.value ? country.selectedOptions[0].dataset.code : '';
    }
}

registry
    .category('public.interactions')
    .add('portal.customer_address', CustomerAddress);
