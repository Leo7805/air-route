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


def _truncate_label(value, limit):
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _route_summary(plan):
    pairs = []
    for link in sorted(plan.route_links, key=lambda item: item.route_id):
        route = link.route
        if route is None:
            continue
        origin = route.origin_iata or f"#{route.origin_airport_id}"
        destination = route.destination_iata or f"#{route.destination_airport_id}"
        pairs.append(f"{origin} -> {destination}")
    if not pairs:
        return "No routes"
    return _truncate_label(" | ".join(pairs), 46)


def _date_range_label(departure, return_date):
    if departure.year == return_date.year:
        return f"{departure:%d %b} - {return_date:%d %b %Y}"
    return f"{departure:%d %b %Y} - {return_date:%d %b %Y}"


def generate_travel_plans_image(plans):
    """Generate a readable plan-level PNG timeline for up to five plans."""
    plan_count = len(plans)
    fig = Figure(figsize=(11.5, max(3.6, plan_count * 0.95 + 2.2)), dpi=120)
    ax = fig.add_subplot(111)

    start_dates = [plan.departure_date for plan in plans]
    end_dates = [plan.return_date for plan in plans]
    first_date = min(start_dates)
    last_date = max(end_dates)
    visible_days = max(1, (last_date - first_date).days + 1)
    label_padding = max(7, round(visible_days * 0.18))

    for index, plan in enumerate(plans):
        start = mdates.date2num(plan.departure_date)
        duration = (plan.return_date - plan.departure_date).days + 1
        ax.barh(
            index,
            duration,
            left=start,
            height=0.38,
            color="#4263B8",
            edgecolor="#2F4A8A",
            linewidth=0.7,
        )
        ax.text(
            start + duration + label_padding * 0.08,
            index,
            _date_range_label(plan.departure_date, plan.return_date),
            va="center",
            ha="left",
            fontsize=8.5,
            color="#334155",
        )

    labels = [
        (
            f"{_truncate_label(plan.name, 32)} "
            f"({len(plan.route_links)} route"
            f"{'' if len(plan.route_links) == 1 else 's'})\n"
            f"{_route_summary(plan)}"
        )
        for plan in plans
    ]
    ax.set_yticks(range(len(plans)), labels)
    ax.invert_yaxis()
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(locator, show_offset=False)
    )
    ax.set_xlim(
        mdates.date2num(first_date) - label_padding * 0.25,
        mdates.date2num(last_date) + label_padding,
    )
    ax.tick_params(axis="y", length=0, pad=10, labelsize=9)
    ax.tick_params(axis="x", labelsize=9)
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
    fig.subplots_adjust(left=0.31, right=0.97, top=0.84, bottom=0.18)

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
