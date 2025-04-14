resource "aws_instance" "bluecore_dev" {
  ami                         = "ami-0892d3c7ee96c0bf7"
  instance_type               = "m7i-flex.2xlarge"
  subnet_id                   = aws_subnet.bluecore-dev-public-3.id
  vpc_security_group_ids      = [aws_security_group.bc_dev_sg.id, aws_security_group.bc_dev_ui_sg.id]
  associate_public_ip_address = "true"
  key_name                    = "bc-dev"

  root_block_device {
    volume_type = "gp2"
    volume_size = 120
  }

  tags = {
    name      = "bluecore_dev"
    terraform = "true"
    project   = "bluecore"
  }
}

resource "aws_key_pair" "bc-dev" {
  key_name   = "bc-dev"
  public_key = file("./assets/key.bc-dev.pub")
}

resource "aws_security_group" "bc_dev_sg" {
  name        = "bc-dev-sg"
  description = "Allow inbound traffic from bluecore devs "
  vpc_id      = aws_vpc.bluecore-dev.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "TCP"
    cidr_blocks = ["171.66.132.0/23", "171.66.134.0/23"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "bc-dev-sg"
    Terraform = "true"
  }
}

resource "aws_security_group" "bc_dev_ui_sg" {
  name        = "bc-dev-ui-sg"
  description = "Allow inbound apache traffic for ui"
  vpc_id      = aws_vpc.bluecore-dev.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "TCP"
    cidr_blocks = [aws_subnet.bluecore-dev-public-1.cidr_block,aws_subnet.bluecore-dev-public-2.cidr_block,aws_subnet.bluecore-dev-public-3.cidr_block]
  }

  tags = {
    Name      = "bc-dev-ui-sg"
    Terraform = "true"
  }
}
