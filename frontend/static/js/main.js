// JavaScript for Bangalore Climate Analytics System

$(document).ready(function() {
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    
    
    // Form validation enhancement
    $('form').on('submit', function(e) {
        var requiredFields = $(this).find('[required]');
        var isValid = true;
        
        requiredFields.each(function() {
            if (!$(this).val()) {
                $(this).addClass('is-invalid');
                isValid = false;
            } else {
                $(this).removeClass('is-invalid').addClass('is-valid');
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            alert('Please fill all required fields.');
        }
    });
    
    // Real-time input validation for climate values
    $('#rainfall').on('input', function() {
        var value = parseFloat($(this).val());
        if (value < 0 || value > 500) {
            $(this).addClass('is-invalid');
            $(this).next('.invalid-feedback').remove();
            $(this).after('<div class="invalid-feedback">Rainfall should be between 0 and 500 mm</div>');
        } else {
            $(this).removeClass('is-invalid').addClass('is-valid');
        }
    });
    
    $('#temperature').on('input', function() {
        var value = parseFloat($(this).val());
        if (value < 10 || value > 45) {
            $(this).addClass('is-invalid');
            $(this).next('.invalid-feedback').remove();
            $(this).after('<div class="invalid-feedback">Temperature should be between 10°C and 45°C</div>');
        } else {
            $(this).removeClass('is-invalid').addClass('is-valid');
        }
    });
    
    $('#humidity').on('input', function() {
        var value = parseFloat($(this).val());
        if (value < 0 || value > 100) {
            $(this).addClass('is-invalid');
            $(this).next('.invalid-feedback').remove();
            $(this).after('<div class="invalid-feedback">Humidity should be between 0% and 100%</div>');
        } else {
            $(this).removeClass('is-invalid').addClass('is-valid');
        }
    });
    
    // Interactive demo: Update CES prediction in real-time
    function updateCESPreview() {
        var rainfall = parseFloat($('#rainfall').val()) || 0;
        var temperature = parseFloat($('#temperature').val()) || 0;
        var humidity = parseFloat($('#humidity').val()) || 0;
        
        // Normal values for Bangalore
        var normRain = 108.5;
        var normTemp = 24.8;
        var normHum = 65.0;
        var stdRain = 85.3;
        var stdTemp = 3.2;
        var stdHum = 15.5;
        
        var zRain = Math.abs((rainfall - normRain) / (stdRain + 0.001));
        var zTemp = Math.abs((temperature - normTemp) / (stdTemp + 0.001));
        var zHum = Math.abs((humidity - normHum) / (stdHum + 0.001));
        
        var ces = (0.4 * zRain + 0.3 * zTemp + 0.3 * zHum);
        
        var condition = ces >= 2 ? 'Extreme' : (ces >= 1 ? 'Moderate' : 'Normal');
        var color = ces >= 2 ? 'danger' : (ces >= 1 ? 'warning' : 'success');
        
        $('#cesPreview').html(`
            <div class="alert alert-${color} mt-3">
                <strong>Current CES Preview:</strong> ${ces.toFixed(3)} 
                <span class="badge bg-${color}">${condition}</span>
            </div>
        `);
    }
    
    // Bind input events for CES preview
    $('#rainfall, #temperature, #humidity').on('input', updateCESPreview);
    
    // Initialize plotly charts on dashboard
    if ($('#climateTrendChart').length) {
        var trace1 = {
            x: [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020, 2024],
            y: [24.2, 24.3, 24.4, 24.5, 24.6, 24.8, 25.0, 25.2, 25.3],
            mode: 'lines+markers',
            name: 'Temperature Trend',
            line: {color: '#ee5a24', width: 3},
            marker: {size: 8}
        };
        
        var trace2 = {
            x: [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020, 2024],
            y: [100, 102, 105, 108, 110, 112, 115, 118, 108.5],
            mode: 'lines+markers',
            name: 'Rainfall Trend',
            line: {color: '#3498db', width: 3},
            marker: {size: 8}
        };
        
        var layout = {
            title: 'Historical Climate Trends (1950-2024)',
            xaxis: {title: 'Year'},
            yaxis: {title: 'Value'},
            hovermode: 'closest',
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        };
        
        Plotly.newPlot('climateTrendChart', [trace1, trace2], layout);
    }
    
    // Export data functionality
    $('#exportData').on('click', function() {
        var table = $('#forecastTable').DataTable();
        var data = table.rows().data().toArray();
        var csv = convertToCSV(data);
        downloadCSV(csv, 'climate_forecast_data.csv');
    });
    
    function convertToCSV(data) {
        var headers = Object.keys(data[0]);
        var csvRows = [];
        csvRows.push(headers.join(','));
        
        for (var i = 0; i < data.length; i++) {
            var values = headers.map(function(header) {
                return '"' + (data[i][header] || '').replace(/"/g, '""') + '"';
            });
            csvRows.push(values.join(','));
        }
        
        return csvRows.join('\n');
    }
    
    function downloadCSV(csv, filename) {
        var blob = new Blob([csv], { type: 'text/csv' });
        var link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        link.click();
        URL.revokeObjectURL(link.href);
    }
    
    // Scroll to top button
    var scrollBtn = $('<button class="btn btn-primary rounded-circle position-fixed" style="bottom: 20px; right: 20px; z-index: 1000; width: 50px; height: 50px;"><i class="fas fa-arrow-up"></i></button>');
    $('body').append(scrollBtn);
    
    scrollBtn.hide();
    
    $(window).scroll(function() {
        if ($(this).scrollTop() > 300) {
            scrollBtn.fadeIn();
        } else {
            scrollBtn.fadeOut();
        }
    });
    
    scrollBtn.click(function() {
        $('html, body').animate({scrollTop: 0}, 500);
    });
    
    // Animate numbers on dashboard
    $('.count-up').each(function() {
        var $this = $(this);
        var countTo = parseFloat($this.text());
        $({ countNum: 0 }).animate({
            countNum: countTo
        }, {
            duration: 2000,
            easing: 'linear',
            step: function() {
                $this.text(Math.floor(this.countNum));
            },
            complete: function() {
                $this.text(countTo);
            }
        });
    });
});

// Climate condition color mapping
function getClimateColor(condition) {
    switch(condition) {
        case 'Extreme': return '#dc3545';
        case 'Moderate': return '#ffc107';
        default: return '#28a745';
    }
}

// Helper function to format date
function formatDate(date) {
    var d = new Date(date);
    return d.toLocaleDateString('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}