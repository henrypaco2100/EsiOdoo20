"""Pure grouping key shared by production planning and regression tests."""
def production_key(template_id, values, grouped_attributes, product_id):
    grouped_attributes = set(grouped_attributes)
    if not any(attribute in grouped_attributes for attribute, value in values):
        return (template_id, ('product', product_id))
    return (template_id, tuple(sorted((attribute, value) for attribute, value in values
                                     if attribute not in grouped_attributes)))
