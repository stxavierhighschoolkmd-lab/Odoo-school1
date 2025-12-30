import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";

import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { EventRegistrationPopup } from "@pos_event/app/components/popup/event_registration_popup/event_registration_popup";

patch(OrderSummary.prototype, {
    async onOrderlineLongPress(ev, orderline) {
        if (!orderline.event_ticket_id) {
            return super.onOrderlineLongPress(ev, orderline);
        }
        const event = orderline.event_ticket_id.event_id;
        const registrationJson = {};
        orderline.event_registration_ids.forEach((registration, index) => {
            const answers = {};
            registration.registration_answer_ids.forEach((answer) => {
                answers[answer.question_id.id] =
                    answer.value_text_box ?? answer.value_answer_id?.id;
            });
            registrationJson[index] = answers;
        });

        const result = await makeAwaitable(this.dialog, EventRegistrationPopup, {
            event,
            data: [
                {
                    product_id: orderline.product_id,
                    qty: orderline.qty,
                    ticket_id: orderline.event_ticket_id,
                    registration_ids: registrationJson,
                },
            ],
        });

        if (result) {
            this._processEventRegistrationResult(result, orderline);
        }
    },

    _processEventRegistrationResult(result, orderline) {
        const questionModel = this.pos.models["event.question"];

        const processAnswer = (originalReg, questionId, answer) => {
            const question = questionModel.get(Number(questionId));
            if (!question) {
                return;
            }
            const existing = originalReg.registration_answer_ids.find(
                (rec) => rec.question_id && rec.question_id.id === question.id
            );
            const isUserField = ["email", "phone", "name", "company_name"]?.includes(
                question.question_type || ""
            );
            if (question.question_type === "simple_choice") {
                this.updateAnswer(answer, existing, originalReg, question, {
                    value_answer_id: { id: Number(answer) },
                });
            } else {
                this.updateAnswer(answer, existing, originalReg, question, {
                    value_text_box: answer,
                });
            }

            return isUserField ? { [question.question_type]: answer } : "";
        };
        const applyAnswersToRegistration = (originalReg, answers) => {
            if (!originalReg || typeof answers !== "object") {
                return;
            }
            // existing values
            const existingVals = {};
            originalReg.registration_answer_ids.forEach((answer) => {
                existingVals[answer.question_id.id] =
                    answer.value_text_box ?? answer.value_answer_id?.id ?? null;
            });
            const userData = {
                name: originalReg.name,
                email: originalReg.email,
                phone: originalReg.phone,
                company_name: originalReg.company_name,
            };
            for (const [questionId, answer] of Object.entries(answers)) {
                const existingValue = existingVals[questionId] ?? "";
                // Update only those questions for which the answer has been modified
                if (existingValue !== answer) {
                    const updatedField = processAnswer(originalReg, questionId, answer);
                    if (updatedField) {
                        Object.assign(userData, updatedField);
                    }
                }
            }
            originalReg.update(userData);
        };
        // Registration Specific Questions
        for (const registrations of Object.values(result.byRegistration)) {
            for (const [regIdx, answers] of Object.entries(registrations)) {
                const originalReg = orderline.event_registration_ids[regIdx];
                applyAnswersToRegistration(originalReg, answers);
            }
        }
        // Global Questions
        for (const originalReg of orderline.event_registration_ids) {
            applyAnswersToRegistration(originalReg, result.byOrder);
        }
    },

    updateAnswer(answer, existing, originalReg, question, values) {
        if (answer) {
            const vals = {
                ...values,
                question_id: question.id,
                registration_id: originalReg,
            };
            existing
                ? existing.update(values)
                : this.pos.models["event.registration.answer"].create(vals);
        } else if (existing) {
            existing.delete();
        }
    },
});
