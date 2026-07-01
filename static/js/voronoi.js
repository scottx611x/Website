$( document ).ready(function() {
    var svg = d3.select("svg");
    // The effect sits behind the page content, so listen on the whole window —
    // otherwise the content on top swallows the mouse and the effect looks dead.
    d3.select(window).on("mousemove.voronoi touchmove.voronoi", moved);

    height = window.innerHeight;
    width = window.innerWidth;

    var sites = d3.range(50)
        .map(function(d) { return [Math.random() * width, Math.random() * height]; });

    var voronoi = d3.voronoi()
        .extent([[-1, -1], [width + 1, height + 1]]);

    var polygon = svg.append("g")
        .attr("class", "polygons")
      .selectAll("path")
      .data(voronoi.polygons(sites))
      .enter().append("path")
        .call(redrawPolygon);

    var link = svg.append("g")
        .attr("class", "links")
      .selectAll("line")
      .data(voronoi.links(sites))
      .enter().append("line")
        .call(redrawLink);

    var site = svg.append("g")
        .attr("class", "sites")
      .selectAll("circle")
      .data(sites)
      .enter().append("circle")
        .attr("r", 2.5)
        .call(redrawSite);

    function moved() {
      var e = d3.event, t = e.touches && e.touches[0];
      sites[0] = [t ? t.clientX : e.clientX, t ? t.clientY : e.clientY];
      redraw();
    }

    function redraw() {
      var diagram = voronoi(sites);
      polygon = polygon.data(diagram.polygons()).call(redrawPolygon);
      link = link.data(diagram.links()), link.exit().remove();
      link = link.enter().append("line").merge(link).call(redrawLink);
      site = site.data(sites).call(redrawSite);
    }

    function redrawPolygon(polygon) {
      polygon
          .attr("d", function(d) { return d ? "M" + d.join("L") + "Z" : null; });

    }

    function redrawLink(link) {
      link
          .attr("x1", function(d) { return d.source[0]; })
          .attr("y1", function(d) { return d.source[1]; })
          .attr("x2", function(d) { return d.target[0]; })
          .attr("y2", function(d) { return d.target[1]; });
    }

    function redrawSite(site) {
      site
          .attr("cx", function(d) { return d[0]; })
          .attr("cy", function(d) { return d[1]; });
    }
});