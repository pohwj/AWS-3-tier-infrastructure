import boto3

# Initialize a Boto3 EC2 client
ec2 = boto3.client('ec2')

# Create a VPC
vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
vpc_id = vpc['Vpc']['VpcId']


print(f"VPC Created: {vpc_id}")

# Create an Internet Gateway and attach to the VPC
igw = ec2.create_internet_gateway()
igw_id = igw['InternetGateway']['InternetGatewayId']
ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)

print(f"Internet Gateway Created: {igw_id}")

# Create Public Subnets
public_subnet1 = ec2.create_subnet(CidrBlock='10.0.1.0/24', VpcId=vpc_id, AvailabilityZone='ap-southeast-1a')
public_subnet2 = ec2.create_subnet(CidrBlock='10.0.2.0/24', VpcId=vpc_id, AvailabilityZone='ap-southeast-1b')
public_subnet1_id = public_subnet1['Subnet']['SubnetId']
public_subnet2_id = public_subnet2['Subnet']['SubnetId']


print(f"Public Subnet 1: {public_subnet1_id}")
print(f"Public Subnet 2: {public_subnet2_id}")

# Create Private Subnets
private_subnet1 = ec2.create_subnet(CidrBlock='10.0.3.0/24', VpcId=vpc_id, AvailabilityZone='ap-southeast-1a')
private_subnet2 = ec2.create_subnet(CidrBlock='10.0.4.0/24', VpcId=vpc_id, AvailabilityZone='ap-southeast-1b')
private_subnet1_id = private_subnet1['Subnet']['SubnetId']
private_subnet2_id = private_subnet2['Subnet']['SubnetId']

print(f"Private Subnet 1: {private_subnet1_id}")
print(f"Private Subnet 2: {private_subnet2_id}")

# Create a Route Table for public subnets
pub_route_table = ec2.create_route_table(VpcId=vpc_id)
pub_route_table_id = pub_route_table['RouteTable']['RouteTableId']
ec2.create_route(DestinationCidrBlock='0.0.0.0/0', GatewayId=igw_id, RouteTableId=pub_route_table_id)

print(f"Public Route Table Created: {pub_route_table_id}")

# Associate the Route Table with public subnets
ec2.associate_route_table(RouteTableId=pub_route_table_id, SubnetId=public_subnet1_id)
ec2.associate_route_table(RouteTableId=pub_route_table_id, SubnetId=public_subnet2_id)

# Allocate Elastic IP for NAT Gateway in each AZ
eip1 = ec2.allocate_address(Domain='vpc')
eip2 = ec2.allocate_address(Domain='vpc')
eip1_id = eip1['AllocationId']
eip2_id = eip2['AllocationId']

# Create NAT Gateway in each AZ
nat_gw1 = ec2.create_nat_gateway(SubnetId=public_subnet1_id, AllocationId=eip1_id)
nat_gw2 = ec2.create_nat_gateway(SubnetId=public_subnet2_id, AllocationId=eip2_id)
nat_gw1_id = nat_gw1['NatGateway']['NatGatewayId']
nat_gw2_id = nat_gw2['NatGateway']['NatGatewayId']

print(f"NAT Gateway 1 Created: {nat_gw1_id}")
print(f"NAT Gateway 2 Created: {nat_gw2_id}")

# Create route tables for private subnets in each AZ
priv_route_table1 = ec2.create_route_table(VpcId=vpc_id)
priv_route_table2 = ec2.create_route_table(VpcId=vpc_id)

priv_route_table1_id = priv_route_table1['RouteTable']['RouteTableId']
priv_route_table2_id = priv_route_table2['RouteTable']['RouteTableId']


print(f"Private Route Table 1 Created: {priv_route_table1_id}")
print(f"Private Route Table 2 Created: {priv_route_table2_id}")

# Get NAT Gateway information
nat_gw1_info = ec2.describe_nat_gateways(NatGatewayIds=[nat_gw1_id])
nat_gw2_info = ec2.describe_nat_gateways(NatGatewayIds=[nat_gw2_id])

# Get NAT Gateway status
nat_gw1_status = nat_gw1_info['NatGateways'][0]['State']
nat_gw2_status = nat_gw2_info['NatGateways'][0]['State']

while nat_gw1_status != 'available' or nat_gw2_status != 'available':
    
    print("waiting for NAT Gateways to become available...")

# Create routes in private route tables to NAT Gateways
ec2.create_route(RouteTableId=priv_route_table1_id, DestinationCidrBlock='0.0.0.0/0', NatGatewayId=nat_gw1_id)
ec2.create_route(RouteTableId=priv_route_table2_id, DestinationCidrBlock='0.0.0.0/0', NatGatewayId=nat_gw2_id)

# Associate private subnets with private route tables
ec2.associate_route_table(RouteTableId=priv_route_table1_id, SubnetId=private_subnet1_id)
ec2.associate_route_table(RouteTableId=priv_route_table2_id, SubnetId=private_subnet2_id)

print(f"NAT Gateway 1 associated with Private Route Table 1")
print(f"NAT Gateway 2 associated with Private Route Table 2")

# Create security group for external load balancer
sg1 = ec2.create_security_group(

    GroupName='Internetfacing-lb-sg',
    Description='Security group for external load balancer',
    VpcId=vpc_id

)

sg1_id = sg1['GroupId']

# Add inbound rules to security group
ec2.authorize_security_group_ingress(

    GroupId=sg1_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
        },
    ]
)


print(f"Internet Facing Security Group Created: {sg1_id}")


# Create security group for web tier
sg2 = ec2.create_security_group(

    GroupName='Webtier-sg',
    Description='Security group for web tier',
    VpcId=vpc_id

)

sg2_id = sg2['GroupId']


# Add inbound rules to web tier security group
ec2.authorize_security_group_ingress(

    GroupId=sg2_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'UserIdGroupPairs': [{'GroupId': sg1_id}]
            
        },

        {   
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': '0.0.0.0/0'}]

        },
    ]
)

print(f"Web Tier Security Group Created: {sg2_id}")


# Create security group for database tier
sg4 = ec2.create_security_group(

    GroupName='DB-sg',
    Description='Security group for database tier',
    VpcId=vpc_id

)

sg4_id = sg4['GroupId']


# Add inbound rules to database tier security group
ec2.authorize_security_group_ingress(

    GroupId=sg4_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 3306,
            'ToPort': 3306,
            'UserIdGroupPairs': [{'GroupId': sg2_id}]
        },
    ]
)

print(f"Database Tier Security Group Created: {sg4_id}")














