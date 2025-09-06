class AddPartitionedCookie:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)

        for name in ("csrftoken", "sessionid"):
            morsel = resp.cookies.get(name)
            if not morsel:
                continue

            # ensure cross-site friendly flags
            morsel["secure"] = True
            morsel["samesite"] = "None"

            # teach the morsel about the Partitioned attribute and set it
            if "partitioned" not in morsel._reserved:
                morsel._reserved["partitioned"] = "Partitioned"
            morsel["partitioned"] = True  # just like Secure/HttpOnly flags

        return resp
