import { ImStatus } from "@mail/core/common/im_status";
import { ThreadIcon } from "@mail/core/common/thread_icon";

import { Component } from "@odoo/owl";

let nextId = 0;

export class DiscussAvatar extends Component {
    static template = "mail.DiscussAvatar";
    static props = [
        "channel?",
        "member?",
        "persona?",
        "thread?",
        "size?",
        "typing?",
        "className?",
        "imgRoundedClass?",
        "user?",
    ];
    static defaultProps = { className: "", size: 32, typing: true };
    static components = { ImStatus, ThreadIcon };

    setup() {
        super.setup();
        this.uniqueId = `mail.DiscussAvatar.${nextId++}`;
    }

    get channel() {
        return this.props.channel ?? this.props.thread?.channel;
    }

    get persona() {
        return this.props.user?.partner_id || this.props.persona || this.props.member?.persona;
    }

    get thread() {
        return this.props.thread ?? this.props.channel?.thread;
    }

    get isTyping() {
        if (!this.props.typing) {
            return false;
        }
        if (this.channel) {
            return this.channel.hasOtherMembersTyping;
        }
        if (this.props.member) {
            return this.props.member.isTyping;
        }
        return false;
    }

    get showIcon() {
        if (this.channel) {
            if (
                this.channel.channel_type === "chat" &&
                !this.channel.correspondent.persona.im_status
            ) {
                return false;
            }
            return this.channel.showThreadIcon({ ignoreTyping: !this.props.typing });
        }
        return Boolean(this.props.member?.im_status || this.persona?.im_status);
    }

    get user() {
        return this.props.user || this.persona?.main_user_id;
    }
}
