from app.core.forms import Form, FormField

FORMS: tuple[Form, ...] = (
    Form(
        name="contact",
        fields=(
            FormField("name", required=True, min_length=2, max_length=100),
            FormField("email", type="email", required=True),
            FormField("phone", type="tel"),
            FormField("topic", type="select", options=("question", "order", "other")),
            FormField("message", type="textarea", required=True, min_length=10),
            FormField("consent", type="consent"),
        ),
    ),
)
