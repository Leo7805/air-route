import json
from io import BytesIO

from flask import send_file
from matplotlib import dates as mdates
from matplotlib.figure import Figure

from .aviation import route_to_dict
from .travel_plans import travel_plan_to_dict


def export_plan_to_dict(plan):
    result = travel_plan_to_dict(plan)
    result["routes"] = [
        route_to_dict(link.route, include_related=True)
        for link in sorted(plan.route_links, key=lambda link: link.route_id)
    ]
    return result


def json_export_response(plans):
    content = json.dumps(
        {"plans": [export_plan_to_dict(plan) for plan in plans]},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    return send_file(
        BytesIO(content),
        mimetype="application/json",
        as_attachment=True,
        download_name="travel-plans.json",
    )


def generate_travel_plans_image(plans):
    """Generate the existing PNG timeline for up to five future plans."""
    fig = Figure(figsize=(11, max(3.5, len(plans) * 0.9 + 2)), dpi=120)
    ax = fig.add_subplot(111)

    for index, plan in enumerate(plans):
        start = mdates.date2num(plan.departure_date)
        duration = (plan.return_date - plan.departure_date).days + 1
        ax.barh(index, duration, left=start, height=0.55, color="#4263B8")

    labels = [
        f"{plan.name[:30]} ({len(plan.route_links)} routes)" for plan in plans
    ]
    ax.set_yticks(range(len(plans)), labels)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_title(
        "Upcoming Travel Plans",
        fontsize=17,
        fontweight="bold",
        loc="left",
        pad=20,
    )
    ax.set_xlabel("Travel dates")
    ax.grid(axis="x", alpha=0.2)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()

    image = BytesIO()
    fig.savefig(image, format="png")
    image.seek(0)
    return image


def png_export_response(plans, image_generator=generate_travel_plans_image):
    return send_file(
        image_generator(plans),
        mimetype="image/png",
        as_attachment=False,
        download_name="upcoming-travel-plans.png",
    )
