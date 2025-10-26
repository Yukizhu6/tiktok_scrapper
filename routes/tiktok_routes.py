from flask import Blueprint, jsonify, request

from scrapers.tiktok_base import collect_explore_items
from scrapers.tiktok_search import search_videos_by_keywords


tiktok_bp = Blueprint("tiktok", __name__, url_prefix="/tiktok")


@tiktok_bp.get("/explore")
def explore():
    # number: how many items to return, default 10
    number_arg = request.args.get("number", "10").strip()
    try:
        number = int(number_arg)
        if number <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "number must be a positive integer"}), 400

    try:
        # Use non-headless to improve anti-bot reliability during scraping
        items = collect_explore_items(number=number, headless=False)
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tiktok_bp.get("/search")
def search():
    keywords = request.args.get("keywords", "").strip()
    if not keywords:
        return jsonify({"error": "please keywords argument"}), 400

    number_arg = request.args.get("number", "10").strip()
    try:
        number = int(number_arg)
        if number <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "number must be a positive integer"}), 400

    try:
        video_links = search_videos_by_keywords(keywords)
        limited = video_links[:number]
        return jsonify({
            "keywords": keywords,
            "count": len(limited),
            "videos": limited,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

