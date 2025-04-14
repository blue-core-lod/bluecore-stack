resource "aws_acm_certificate" "dev_cert" {
  domain_name       = "dev.bcld.info"
  validation_method = "DNS"
}

resource "aws_alb" "bluecore_dev_alb" {
  name            = "bluecore-dev-alb"
  subnets         = [aws_subnet.bluecore-dev-public-1.id,aws_subnet.bluecore-dev-public-2.id,aws_subnet.bluecore-dev-public-3.id]
  security_groups = [aws_security_group.bluecore_dev_alb_sg.id]

  tags = {
    Name        = "bluecore-dev-alb"
  }
}

resource "aws_security_group" "bluecore_dev_alb_sg" {
  name        = "bluecore-dev-alb-sg"
  description = "Allow HTTP/HTTPS into ALB"
  vpc_id      = aws_vpc.bluecore-dev.id

  tags = {
    Name = "bluecore-dev-alb-sg"
  }
}

resource "aws_security_group_rule" "http_ingress" {
  type        = "ingress"
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
  from_port   = 80
  to_port     = 80

  security_group_id = aws_security_group.bluecore_dev_alb_sg.id
}

resource "aws_security_group_rule" "https_ingress" {
  type        = "ingress"
  protocol    = "tcp"
  cidr_blocks = ["0.0.0.0/0"]
  from_port   = 443
  to_port     = 443

  security_group_id = aws_security_group.bluecore_dev_alb_sg.id
}

resource "aws_security_group_rule" "egress" {
  type        = "egress"
  protocol    = "-1"
  cidr_blocks = ["0.0.0.0/0"]
  from_port   = 0
  to_port     = 0

  security_group_id = aws_security_group.bluecore_dev_alb_sg.id
}

resource "aws_alb_target_group" "bluecore_dev_alb_default_tg" {
  name        = "bluecore-dev-alb"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = aws_vpc.bluecore-dev.id
  target_type = "ip"

  health_check {
    path    = "/"
    matcher = "200"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_target_group_attachment" "bluecore_dev_alb_default_tg_attachment" {
  target_group_arn = aws_alb_target_group.bluecore_dev_alb_default_tg.id
  target_id        = aws_instance.bluecore_dev.private_ip
   port             = 443
}

resource "aws_alb_listener" "bluecore_dev_alb_http_listener" {
  load_balancer_arn = aws_alb.bluecore_dev_alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_alb_listener" "bluecore_dev_alb_https_listener" {
  load_balancer_arn = aws_alb.bluecore_dev_alb.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = aws_acm_certificate.dev_cert.arn

  default_action {
    target_group_arn = aws_alb_target_group.bluecore_dev_alb_default_tg.id
    type             = "forward"
  }
}
