/** @odoo-module **/
import { registry } from "@web/core/registry";
import {
    Many2ManyTagsColorDotField,
    many2ManyTagsColorDotField,
} from "@web/views/fields/many2many_tags_color_dot/many2many_tags_color_dot_field";

export function sortSizeTags(tags) {
    const number = (tag) => {
        const label = tag.props.text.trim().replace(",", ".");
        return /^\d+(\.\d+)?$/.test(label) ? Number(label) : Infinity;
    };
    return [...tags].sort((a, b) => (number(a) - number(b)) || 0);
}

class TosscanoSizeTagsField extends Many2ManyTagsColorDotField {
    get tags() {
        const tags = super.tags;
        return this.props.record.data.tosscano_is_size ? sortSizeTags(tags) : tags;
    }
}

registry.category("fields").add("tosscano_size_tags", {
    ...many2ManyTagsColorDotField,
    component: TosscanoSizeTagsField,
});
