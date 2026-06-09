resource "aws_sesv2_email_identity" "sender" {
  count = var.ses_sender_email == "" ? 0 : 1

  email_identity = var.ses_sender_email
}
