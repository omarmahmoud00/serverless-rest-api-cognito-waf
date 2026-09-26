"""Architecture diagram for the Serverless To-Do REST API.

Generated with the open-source `diagrams` library (https://diagrams.mingrammer.com).
Regenerate with:  pip install diagrams && python diagram.py
"""
from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import DynamodbTable, DynamodbStreams
from diagrams.aws.devtools import XRay
from diagrams.aws.management import Cloudwatch
from diagrams.aws.network import APIGateway, CloudFront
from diagrams.aws.security import Cognito, WAF, IAMRole
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users

graph_attr = {
    "fontsize": "22",
    "fontname": "Helvetica-Bold",
    "pad": "0.6",
    "nodesep": "0.7",
    "ranksep": "1.1",
    "splines": "spline",
    "bgcolor": "white",
    "labelloc": "t",
}
node_attr = {"fontsize": "12", "fontname": "Helvetica"}
edge_attr = {"fontsize": "11", "fontname": "Helvetica"}


def step(n, text, color="#232F3E", style="solid"):
    return Edge(label=f"({n}) {text}", color=color, fontcolor=color, style=style)


with Diagram(
    "Serverless To-Do REST API  -  Cognito Auth, DynamoDB, WAF, CloudFront, X-Ray",
    filename="architecture-diagram",
    outformat=["png"],
    direction="LR",
    show=False,
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    users = Users("Users\n(browser / SPA)")

    with Cluster("AWS Cloud", graph_attr={"bgcolor": "#F7F9FC", "fontsize": "16"}):
        with Cluster("Edge (global)", graph_attr={"bgcolor": "#FFF4E5", "fontsize": "14"}):
            waf_edge = WAF("AWS WAF (CLOUDFRONT)\nrate limit - geo block\nOWASP / Bot Control")
            cdn = CloudFront("Amazon CloudFront\n/*      -> S3 origin\n/api/* -> API origin")

        with Cluster("AWS Region", graph_attr={"bgcolor": "#EEF6FF", "fontsize": "14"}):
            s3 = S3("S3 bucket\nReact SPA (private,\nOrigin Access Control)")
            cognito = Cognito("Cognito User Pool\nHosted UI - JWT\n(OAuth2 code + PKCE)")

            with Cluster("API layer", graph_attr={"bgcolor": "#F3EEFF", "fontsize": "13"}):
                waf_reg = WAF("AWS WAF (REGIONAL)\norigin-verify header")
                apigw = APIGateway("API Gateway (REST)\nCognito authorizer\nusage plans - stage cache")

            with Cluster("Lambda CRUD handlers (Node.js 22, arm64)", graph_attr={"bgcolor": "#FFF8E1", "fontsize": "13"}):
                fns = [
                    Lambda("createTodo"),
                    Lambda("listTodos"),
                    Lambda("getTodo"),
                    Lambda("updateTodo"),
                    Lambda("deleteTodo"),
                ]

            with Cluster("Data layer", graph_attr={"bgcolor": "#E8F5E9", "fontsize": "13"}):
                ddb = DynamodbTable("DynamoDB 'Todos'\non-demand - 2 GSIs\nPITR - SSE")
                streams = DynamodbStreams("DynamoDB Streams\nNEW_AND_OLD_IMAGES")
                stream_fn = Lambda("streamProcessor\n(per-user stats)")

            with Cluster("Observability & IAM", graph_attr={"bgcolor": "#FCE4EC", "fontsize": "13"}):
                xray = XRay("AWS X-Ray\nservice map / traces")
                cw = Cloudwatch("CloudWatch\nlogs - metrics - alarms")
                iam = IAMRole("IAM roles\n(least privilege)")

    # 1 - request enters through CloudFront, inspected by WAF
    users >> step(1, "HTTPS") >> cdn
    waf_edge - Edge(style="dashed", color="#D13212", label="inspects") - cdn
    # 2 - static assets
    cdn >> step(2, "static assets (OAC)", "#3F8624") >> s3
    # 3 - sign-in via hosted UI
    users >> step(3, "sign-in / tokens", "#BF0816", "dashed") >> cognito
    # 4 - API traffic
    cdn >> step(4, "/api/* + X-Origin-Verify", "#8C4FFF") >> waf_reg
    waf_reg >> Edge(color="#8C4FFF") >> apigw
    # 5 - JWT validation
    apigw >> step(5, "validate JWT", "#BF0816", "dashed") >> cognito
    # 6 - invoke Lambda
    for i, f in enumerate(fns):
        apigw >> (step(6, "invoke (proxy)", "#E7157B") if i == 0 else Edge(color="#E7157B")) >> f
    # 7 - read/write
    for i, f in enumerate(fns):
        f >> (step(7, "CRUD (AWS SDK v3)", "#3F8624") if i == 0 else Edge(color="#3F8624")) >> ddb
    # 8 - stream processing
    ddb >> step(8, "change events", "#3F8624") >> streams >> stream_fn
    stream_fn >> Edge(label="update STATS item", color="#3F8624", style="dashed") >> ddb
    # 9 - tracing and logs
    apigw >> Edge(style="dotted", color="#7D8998") >> xray
    fns[2] >> Edge(label="(9) traces / logs", style="dotted", color="#7D8998") >> xray
    fns[2] >> Edge(style="dotted", color="#7D8998") >> cw
    iam - Edge(style="invis") - cw
