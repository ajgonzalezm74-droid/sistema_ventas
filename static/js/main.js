// API Base URL
const API_BASE = 'http://localhost:5000/api';

// Estado global
let currentTasa = 0;
let carrito = [];
let productosHistorial = [];

// ========== UTILIDADES ==========
function showToast(message, duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

function showLoading() {
    document.getElementById('loading').classList.add('show');
}

function hideLoading() {
    document.getElementById('loading').classList.remove('show');
}

async function fetchAPI(url, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${url}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('Error de conexión');
        return null;
    }
}

// ========== TASA BCV ==========
async function cargarTasa() {
    try {
        const response = await fetch('http://localhost:5000/api/tasa');
        const data = await response.json();
        currentTasa = data.bcv_usd || 0;
        const tasaElement = document.getElementById('tasa_actual');
        if (tasaElement) tasaElement.textContent = currentTasa.toFixed(2);
        return currentTasa;
    } catch (error) {
        console.error('Error cargando tasa:', error);
        return 0;
    }
}

// ========== CLIENTES ==========
async function cargarClientes() {
    const clientesData = await fetchAPI('/clientes');
    if (clientesData) {
        const select = document.getElementById('venta_cliente');
        const lista = document.getElementById('lista_clientes');
        
        if (select) {
            select.innerHTML = '<option value="">Seleccionar cliente</option>';
            clientesData.forEach(cliente => {
                select.innerHTML += `<option value="${cliente.id}">${cliente.nombre}</option>`;
            });
        }
        
        if (lista) {
            lista.innerHTML = clientesData.map(cliente => `
                <div class="cliente-item">
                    <div class="cliente-info">
                        <strong>${cliente.nombre}</strong>
                        <small>📞 ${cliente.telefono || 'Sin teléfono'}</small>
                    </div>
                </div>
            `).join('');
        }
    }
}

async function agregarCliente() {
    const nombre = document.getElementById('cliente_nombre')?.value;
    const telefono = document.getElementById('cliente_telefono')?.value;
    
    if (!nombre) {
        showToast('Ingrese el nombre del cliente');
        return;
    }
    
    showLoading();
    const result = await fetchAPI('/clientes/validar', {
        method: 'POST',
        body: JSON.stringify({ nombre, telefono })
    });
    hideLoading();
    
    if (result && result.success) {
        showToast('✅ Cliente agregado');
        document.getElementById('cliente_nombre').value = '';
        document.getElementById('cliente_telefono').value = '';
        cargarClientes();
        cargarClientesHistorial();
    } else if (result && result.cliente_existente) {
        const usarExistente = confirm(`⚠️ Ya existe un cliente con ese teléfono:\n\n${result.cliente_existente.nombre}\n\n¿Desea seleccionar este cliente?`);
        if (usarExistente) {
            const selectCliente = document.getElementById('venta_cliente');
            if (selectCliente) {
                selectCliente.value = result.cliente_existente.id;
                showToast(`Cliente seleccionado: ${result.cliente_existente.nombre}`);
            }
            document.getElementById('cliente_nombre').value = '';
            document.getElementById('cliente_telefono').value = '';
        }
    } else if (result && result.error) {
        showToast(result.error);
    }
}

async function buscarClientePorNombre() {
    const nombre = document.getElementById('cliente_nombre')?.value;
    if (!nombre || nombre.length < 2) return;
    
    const clientes = await fetchAPI(`/clientes/buscar?nombre=${encodeURIComponent(nombre)}`);
    if (clientes && clientes.length > 0) {
        const lista = document.getElementById('lista_clientes');
        if (lista) {
            lista.innerHTML = clientes.map(cliente => `
                <div class="cliente-item" onclick="seleccionarClienteExistente(${cliente.id}, '${cliente.nombre}')">
                    <div class="cliente-info">
                        <strong>${cliente.nombre}</strong>
                        <small>📞 ${cliente.telefono || 'Sin teléfono'}</small>
                    </div>
                </div>
            `).join('');
        }
    }
}

function seleccionarClienteExistente(id, nombre) {
    const select = document.getElementById('venta_cliente');
    if (select) {
        select.value = id;
        showToast(`Cliente seleccionado: ${nombre}`);
    }
    document.getElementById('cliente_nombre').value = '';
    document.getElementById('cliente_telefono').value = '';
    document.getElementById('lista_clientes').innerHTML = '';
}

// ========== PRODUCTOS ==========
async function cargarProductos() {
    const productosData = await fetchAPI('/productos');
    if (productosData) {
        const select = document.getElementById('venta_producto');
        const lista = document.getElementById('lista_productos');
        
        if (select) {
            select.innerHTML = '<option value="">Seleccionar producto</option>';
            productosData.forEach(prod => {
                select.innerHTML += `<option value="${prod.id}" data-costo="${prod.costo}">${prod.descripcion} (Stock: ${prod.cantidad || 0})</option>`;
            });
        }
        
        if (lista) {
            lista.innerHTML = productosData.map(prod => `
                <div class="producto-item">
                    <div class="producto-info">
                        <strong>${prod.descripcion}</strong>
                        <small>💰 $${prod.costo} | 📦 Stock: ${prod.cantidad || 0}</small>
                    </div>
                    <div class="producto-actions">
                        <button class="btn-icon primary" onclick="mostrarModalReponer(${prod.id}, '${prod.descripcion}', ${prod.costo})">
                            <i class="material-icons">add_box</i>
                        </button>
                    </div>
                </div>
            `).join('');
        }
    }
}

async function agregarProducto() {
    const descripcion = document.getElementById('producto_descripcion')?.value.trim();
    const costo = parseFloat(document.getElementById('producto_costo')?.value);
    const stock = parseInt(document.getElementById('producto_stock')?.value);
    
    if (!descripcion || !costo) {
        showToast('Complete todos los campos');
        return;
    }
    
    showLoading();
    const result = await fetchAPI('/productos', {
        method: 'POST',
        body: JSON.stringify({ descripcion, costo, stock })
    });
    hideLoading();
    
    if (result && result.success) {
        showToast('✅ Producto agregado');
        document.getElementById('producto_descripcion').value = '';
        document.getElementById('producto_costo').value = '';
        document.getElementById('producto_stock').value = '';
        cargarProductos();
    } else if (result && result.error) {
        showToast(result.error);
    }
}

function mostrarModalReponer(id_producto, descripcion, costoActual = null) {
    const cantidad = prompt(`📦 REPONER STOCK\n\nProducto: ${descripcion}\n\nIngrese la cantidad a agregar al inventario:`);
    if (cantidad && parseInt(cantidad) > 0) {
        reponerStock(id_producto, parseInt(cantidad), costoActual);
    }
}

async function reponerStock(id_producto, cantidad, costo = null) {
    showLoading();
    const body = { cantidad };
    if (costo !== null && costo > 0) {
        body.costo = costo;
    }
    
    const result = await fetchAPI(`/productos/reponer/${id_producto}`, {
        method: 'POST',
        body: JSON.stringify(body)
    });
    hideLoading();
    
    if (result && result.success) {
        showToast(`✅ Stock repuesto: +${cantidad} unidades`);
        cargarProductos();
    } else if (result && result.error) {
        showToast(result.error);
    }
}

// ========== CARRITO ==========
function agregarAlCarrito() {
    const productoSelect = document.getElementById('venta_producto');
    const cantidad = parseInt(document.getElementById('venta_cantidad')?.value);
    
    if (!productoSelect?.value) {
        showToast('Seleccione un producto');
        return;
    }
    
    const productoId = parseInt(productoSelect.value);
    const productoNombre = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
    const costoUSD = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
    
    const existente = carrito.find(item => item.id === productoId);
    if (existente) {
        existente.cantidad += cantidad;
    } else {
        carrito.push({
            id: productoId,
            nombre: productoNombre,
            cantidad: cantidad,
            costo_usd: costoUSD
        });
    }
    
    actualizarCarrito();
    document.getElementById('venta_cantidad').value = '1';
}

function actualizarCarrito() {
    const carritoDiv = document.getElementById('carrito_items');
    const totalCarrito = document.getElementById('total_carrito');
    
    if (!carritoDiv) return;
    
    if (carrito.length === 0) {
        carritoDiv.innerHTML = '<p class="empty">Carrito vacío</p>';
        totalCarrito.textContent = '0.00';
        return;
    }
    
    let html = '';
    let total = 0;
    
    carrito.forEach((item, index) => {
        const subtotal = item.costo_usd * item.cantidad * currentTasa;
        total += subtotal;
        
        html += `
            <div class="carrito-item">
                <div class="carrito-info">
                    <strong>${item.nombre}</strong>
                    <small>$${item.costo_usd} x ${item.cantidad}</small>
                    <span>Bs ${subtotal.toFixed(2)}</span>
                </div>
                <button class="btn-icon danger" onclick="eliminarDelCarrito(${index})">
                    <i class="material-icons">delete</i>
                </button>
            </div>
        `;
    });
    
    carritoDiv.innerHTML = html;
    totalCarrito.textContent = total.toFixed(2);
}

function eliminarDelCarrito(index) {
    carrito.splice(index, 1);
    actualizarCarrito();
}

async function registrarVentaMultiple() {
    if (carrito.length === 0) {
        showToast('Agregue productos al carrito');
        return;
    }
    
    const id_cliente = document.getElementById('venta_cliente')?.value;
    const credito = document.getElementById('venta_credito')?.checked;
    
    if (!id_cliente) {
        showToast('Seleccione un cliente');
        return;
    }
    
    const productos = carrito.map(item => ({
        id_producto: item.id,
        cantidad: item.cantidad
    }));
    
    showLoading();
    const result = await fetchAPI('/ventas', {
        method: 'POST',
        body: JSON.stringify({ id_cliente, productos, credito })
    });
    hideLoading();
    
    if (result && result.success) {
        let mensaje = `✅ Venta registrada - Total: Bs ${result.total_bs.toFixed(2)}`;
        if (credito) mensaje += ' (Vendido a CRÉDITO)';
        showToast(mensaje);
        
        carrito = [];
        actualizarCarrito();
        document.getElementById('venta_cliente').value = '';
        document.getElementById('venta_credito').checked = false;
        
        cargarProductos();
        cargarCreditos();
    } else if (result && result.error) {
        showToast(result.error);
    }
}

// ========== CRÉDITOS ==========
async function cargarCreditos() {
    console.log("🔄 Cargando créditos...");
    
    try {
        const response = await fetch('http://localhost:5000/api/creditos/retraso');
        const creditos = await response.json();
        
        console.log("📦 Créditos recibidos:", creditos);
        
        const lista = document.getElementById('lista_creditos');
        
        if (!lista) {
            console.error("❌ No se encontró 'lista_creditos'");
            return;
        }
        
        if (!creditos || creditos.length === 0) {
            lista.innerHTML = '<p class="empty">✅ No hay créditos pendientes</p>';
            return;
        }
        
        let html = '';
        for (const cred of creditos) {
            html += `
                <div class="credito-item">
                    <div class="credito-info">
                        <strong>${cred.nombre || 'Cliente'}</strong>
                        <span class="${cred.badge_class || 'badge-info'}">${cred.estado_texto || 'Pendiente'}</span>
                        <div class="deuda-original">
                            <small>💰 Deuda original: Bs ${(cred.total_original || 0).toFixed(2)}</small>
                            <small>📅 Tasa al vender: Bs ${(cred.tasa_venta || 0).toFixed(2)}</small>
                            <small>💵 Total en USD: $${(cred.total_usd || 0).toFixed(2)}</small>
                        </div>
                        <div class="deuda-actualizada">
                            <strong>💵 Al pagar HOY: Bs ${(cred.total_actualizado || 0).toFixed(2)}</strong>
                            <small>📈 Tasa actual: Bs ${(cred.tasa_actual || 0).toFixed(2)}</small>
                            ${cred.total_pagado > 0 ? `<small>✅ Pagado: Bs ${cred.total_pagado.toFixed(2)}</small>` : ''}
                            ${cred.saldo_pendiente > 0 ? `<small class="warning">⚠️ Saldo pendiente: Bs ${cred.saldo_pendiente.toFixed(2)}</small>` : ''}
                        </div>
                        <small>📦 ${cred.productos || 'Producto'}</small>
                        <small>📅 ${cred.fecha_venta ? cred.fecha_venta.substring(0, 10) : ''}</small>
                    </div>
                    <div class="credito-actions">
                        <button class="btn-icon primary" onclick="verRecibo(${cred.id})" title="Ver Recibo">
                            <i class="material-icons">receipt</i>
                        </button>
                        <button class="btn-icon info" onclick="verReciboCliente(${cred.id_cliente})" title="Ver Estado de Cuenta">
                            <i class="material-icons">description</i>
                        </button>
                        <button class="btn-pagar" onclick="mostrarOpcionesPago(${cred.id}, '${cred.nombre}', ${cred.saldo_pendiente || 0}, ${cred.total_actualizado || 0})">
                            <i class="material-icons">payment</i> Pagar
                        </button>
                    </div>
                </div>
            `;
        }
        
        lista.innerHTML = html;
        console.log("✅ Créditos mostrados");
        
    } catch (error) {
        console.error("❌ Error cargando créditos:", error);
        const lista = document.getElementById('lista_creditos');
        if (lista) lista.innerHTML = '<p class="empty" style="color:red;">Error al cargar créditos</p>';
    }
}

async function verReciboCliente(id_cliente) {
    window.open(`http://localhost:5000/api/ventas/recibo/cliente/${id_cliente}`, '_blank');
}

function mostrarOpcionesPago(id_venta, nombre, saldo_pendiente, total_actualizado) {
    const opcion = confirm(`💰 PAGO DE CRÉDITO\n\nCliente: ${nombre}\nTotal actualizado: Bs ${total_actualizado.toFixed(2)}\nSaldo pendiente: Bs ${saldo_pendiente.toFixed(2)}\n\n✓ Aceptar = Pago COMPLETO\n✓ Cancelar = Pago PARCIAL`);
    
    if (opcion) {
        pagarCreditoCompleto(id_venta);
    } else {
        const monto = prompt(`💰 PAGO PARCIAL\n\nCliente: ${nombre}\nSaldo pendiente: Bs ${saldo_pendiente.toFixed(2)}\n\nIngrese el monto a pagar (Bs):`);
        if (monto && parseFloat(monto) > 0) {
            pagarCreditoParcial(id_venta, parseFloat(monto));
        } else {
            showToast('Pago cancelado');
        }
    }
}

async function pagarCreditoCompleto(id_venta) {
    const confirmar = confirm('⚠️ CONFIRMAR PAGO COMPLETO\n\n¿Está seguro de realizar el PAGO COMPLETO?\n\nSe aplicará la TASA DEL DÍA actual.');
    if (!confirmar) return;
    
    showLoading();
    try {
        const response = await fetch(`http://localhost:5000/api/ventas/pagar/${id_venta}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();
        hideLoading();
        
        if (result && result.success) {
            let mensaje = `✅ PAGO COMPLETADO\n\n💰 Total pagado: Bs ${result.total_pagado_bs.toFixed(2)}\n📉 Tasa venta: Bs ${result.tasa_venta.toFixed(2)}\n📈 Tasa pago: Bs ${result.tasa_pago.toFixed(2)}`;
            if (result.diferencia_tasa !== 0) {
                mensaje += `\n${result.diferencia_tasa > 0 ? '⚠️ Aumentó' : '📉 Disminuyó'} Bs ${Math.abs(result.diferencia_tasa).toFixed(2)} por cambio de tasa`;
            }
            alert(mensaje);
            showToast(`✅ Pago registrado: Bs ${result.total_pagado_bs.toFixed(2)}`);
            cargarCreditos();
            cargarReportes('semanal');
        } else {
            showToast(result?.error || 'Error al procesar el pago');
        }
    } catch (error) {
        hideLoading();
        showToast('Error de conexión');
    }
}

async function pagarCreditoParcial(id_venta, monto) {
    showLoading();
    try {
        const response = await fetch(`http://localhost:5000/api/creditos/pagar-parcial`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id_venta: id_venta, monto: monto, observacion: 'Pago parcial' })
        });
        const result = await response.json();
        hideLoading();
        
        if (result && result.success) {
            alert(`💰 PAGO PARCIAL REGISTRADO\n\n💵 Monto pagado: Bs ${result.monto_pagado.toFixed(2)}\n⚠️ Saldo pendiente: Bs ${result.saldo_pendiente.toFixed(2)}`);
            showToast(`Pago parcial: Bs ${result.monto_pagado.toFixed(2)}`);
            cargarCreditos();
        } else {
            showToast(result?.error || 'Error al procesar el pago parcial');
        }
    } catch (error) {
        hideLoading();
        showToast('Error de conexión');
    }
}

async function verRecibo(id_venta) {
    window.open(`http://localhost:5000/api/ventas/recibo/${id_venta}`, '_blank');
}

// ========== HISTORIAL DE VENTAS ==========
async function cargarClientesHistorial() {
    console.log("🔄 Cargando clientes para historial...");
    
    try {
        const response = await fetch('http://localhost:5000/api/clientes');
        const clientes = await response.json();
        
        const select = document.getElementById('historial_cliente');
        if (!select) return;
        
        if (clientes && clientes.length > 0) {
            select.innerHTML = '<option value="">Seleccionar cliente</option>';
            clientes.forEach(cliente => {
                select.innerHTML += `<option value="${cliente.id}">${cliente.nombre}</option>`;
            });
        } else {
            select.innerHTML = '<option value="">No hay clientes registrados</option>';
        }
    } catch (error) {
        console.error("Error cargando clientes:", error);
    }
}

async function cargarProductosHistorial() {
    console.log("🔄 Cargando productos para historial...");
    
    try {
        const response = await fetch('http://localhost:5000/api/productos');
        const productos = await response.json();
        
        const select = document.getElementById('historial_producto');
        if (!select) return;
        
        if (productos && productos.length > 0) {
            select.innerHTML = '<option value="">Seleccionar producto</option>';
            productos.forEach(prod => {
                select.innerHTML += `<option value="${prod.id}" data-costo="${prod.costo}">${prod.descripcion} ($${prod.costo})</option>`;
            });
        } else {
            select.innerHTML = '<option value="">No hay productos registrados</option>';
        }
    } catch (error) {
        console.error("Error cargando productos:", error);
    }
}

function calcularPreviewHistorial() {
    const productoSelect = document.getElementById('historial_producto');
    const cantidad = parseInt(document.getElementById('historial_cantidad').value) || 1;
    const tasa = parseFloat(document.getElementById('historial_tasa').value) || 0;
    const clienteSelect = document.getElementById('historial_cliente');
    
    if (clienteSelect && clienteSelect.value) {
        document.getElementById('preview_cliente').textContent = clienteSelect.options[clienteSelect.selectedIndex].text;
    }
    
    if (productoSelect && productoSelect.value && tasa > 0) {
        const costoUSD = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
        const totalUSD = costoUSD * cantidad;
        const totalBS = totalUSD * tasa;
        
        document.getElementById('preview_usd').textContent = totalUSD.toFixed(2);
        document.getElementById('preview_bs').textContent = totalBS.toFixed(2);
        document.getElementById('preview_tasa').textContent = tasa.toFixed(2);
        document.getElementById('preview_producto').textContent = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
        document.getElementById('preview_cantidad').textContent = cantidad;
        document.getElementById('historial_preview').style.display = 'block';
    } else {
        document.getElementById('historial_preview').style.display = 'none';
    }
}

async function agregarProductoHistorial() {
    const productoSelect = document.getElementById('historial_producto');
    const cantidad = parseInt(document.getElementById('historial_cantidad').value);
    const tasa = parseFloat(document.getElementById('historial_tasa').value);
    
    if (!productoSelect.value) {
        showToast('Seleccione un producto');
        return;
    }
    
    if (tasa <= 0) {
        showToast('Ingrese la tasa BCV');
        return;
    }
    
    const id_producto = parseInt(productoSelect.value);
    const descripcion = productoSelect.options[productoSelect.selectedIndex].text.split(' (')[0];
    const costo_usd = parseFloat(productoSelect.options[productoSelect.selectedIndex].dataset.costo);
    const subtotal = costo_usd * cantidad * tasa;
    
    productosHistorial.push({
        id_producto: id_producto,
        descripcion: descripcion,
        cantidad: cantidad,
        subtotal: subtotal,
        tasa: tasa
    });
    
    actualizarListaHistorial();
    
    document.getElementById('historial_producto').value = '';
    document.getElementById('historial_cantidad').value = '1';
    document.getElementById('historial_tasa').value = '';
    document.getElementById('historial_preview').style.display = 'none';
    
    showToast('Producto agregado al carrito');
}

function actualizarListaHistorial() {
    const container = document.getElementById('lista_productos_historial');
    if (!container) return;
    
    if (productosHistorial.length === 0) {
        container.innerHTML = '<div style="text-align:center; color:#999;">No hay productos agregados</div>';
        return;
    }
    
    let html = '';
    let total = 0;
    
    productosHistorial.forEach((item, index) => {
        total += item.subtotal;
        html += `
            <div class="carrito-item">
                <div class="carrito-info">
                    <strong>${item.descripcion}</strong>
                    <small>x${item.cantidad}</small>
                    <span>Bs ${item.subtotal.toFixed(2)}</span>
                </div>
                <button class="btn-icon danger" onclick="eliminarProductoHistorial(${index})">
                    <i class="material-icons">delete</i>
                </button>
            </div>
        `;
    });
    
    html += `<div class="carrito-total"><strong>Total: Bs ${total.toFixed(2)}</strong></div>`;
    container.innerHTML = html;
}

function eliminarProductoHistorial(index) {
    productosHistorial.splice(index, 1);
    actualizarListaHistorial();
}

async function guardarVentaHistorica() {
    if (productosHistorial.length === 0) {
        showToast('Agregue productos al carrito');
        return;
    }
    
    const id_cliente = document.getElementById('historial_cliente').value;
    const fecha = document.getElementById('historial_fecha').value;
    
    if (!id_cliente) {
        showToast('Seleccione un cliente');
        return;
    }
    
    if (!fecha) {
        showToast('Ingrese la fecha de compra');
        return;
    }
    
    const tasaVenta = productosHistorial[0].tasa;
    const productos = productosHistorial.map(item => ({
        id_producto: item.id_producto,
        cantidad: item.cantidad
    }));
    
    showLoading();
    
    const result = await fetchAPI('/ventas', {
        method: 'POST',
        body: JSON.stringify({ 
            id_cliente: parseInt(id_cliente), 
            productos: productos, 
            credito: true 
        })
    });
    
    if (result && result.success) {
        await fetch(`http://localhost:5000/api/ventas/actualizar-fecha/${result.id_venta}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha: fecha, tasa: tasaVenta })
        });
        
        showToast('✅ Venta histórica registrada');
        productosHistorial = [];
        actualizarListaHistorial();
        document.getElementById('historial_cliente').value = '';
        document.getElementById('historial_fecha').value = '';
        cargarCreditos();
    } else {
        showToast(result?.error || 'Error al registrar venta');
    }
    hideLoading();
}

// ========== REPORTES ==========
async function cargarReportes(tipo) {
    showLoading();
    let data = await fetchAPI(`/reportes/ventas?periodo=${tipo}`);
    hideLoading();
    
    const container = document.getElementById('reporte_resultados');
    if (!container) return;
    
    if (!data || data.length === 0) {
        container.innerHTML = '<p class="empty">📊 No hay datos disponibles</p>';
        return;
    }
    
    if (tipo === 'productos') {
        container.innerHTML = `
            <div class="reporte-header">
                <div class="reporte-item header">
                    <strong>Producto</strong>
                    <strong>Unidades</strong>
                    <strong>Contado (Bs)</strong>
                    <strong>Crédito Pendiente (Bs)</strong>
                    <strong>Crédito Pagado (Bs)</strong>
                    <strong>Total Bs</strong>
                </div>
                ${data.map(p => `
                    <div class="reporte-item">
                        <span>${p.producto || 'Producto'}</span>
                        <span>${p.unidades_vendidas || 0}</span>
                        <span class="success-text">Bs ${(p.total_contado || 0).toFixed(2)}</span>
                        <span class="warning-text">Bs ${(p.total_credito_pendiente || 0).toFixed(2)}</span>
                        <span class="info-text">Bs ${(p.total_credito_pagado || 0).toFixed(2)}</span>
                        <span class="total-text">Bs ${(p.total_bs || 0).toFixed(2)}</span>
                    </div>
                `).join('')}
                <div class="reporte-item total">
                    <strong>TOTALES</strong>
                    <span></span>
                    <strong class="success-text">Bs ${data.reduce((sum, p) => sum + (p.total_contado || 0), 0).toFixed(2)}</strong>
                    <strong class="warning-text">Bs ${data.reduce((sum, p) => sum + (p.total_credito_pendiente || 0), 0).toFixed(2)}</strong>
                    <strong class="info-text">Bs ${data.reduce((sum, p) => sum + (p.total_credito_pagado || 0), 0).toFixed(2)}</strong>
                    <strong class="total-text">Bs ${data.reduce((sum, p) => sum + (p.total_bs || 0), 0).toFixed(2)}</strong>
                </div>
            </div>
        `;
    } else {
        // Reportes semanal y mensual
        container.innerHTML = `
            <div class="reporte-header">
                <div class="reporte-item header">
                    <strong>Período</strong>
                    <strong>Ventas</strong>
                    <strong>Contado (Bs)</strong>
                    <strong>Crédito Pendiente (Bs)</strong>
                    <strong>Crédito Pagado (Bs)</strong>
                    <strong>Total Bs</strong>
                </div>
                ${data.map(r => `
                    <div class="reporte-item">
                        <span>${r.periodo || 'Sin fecha'}</span>
                        <span>${r.total_ventas || 0}</span>
                        <span class="success-text">Bs ${(r.total_contado || 0).toFixed(2)}</span>
                        <span class="warning-text">Bs ${(r.total_credito_pendiente || 0).toFixed(2)}</span>
                        <span class="info-text">Bs ${(r.total_credito_pagado || 0).toFixed(2)}</span>
                        <span class="total-text">Bs ${(r.total_bs || 0).toFixed(2)}</span>
                    </div>
                `).join('')}
                <div class="reporte-item total">
                    <strong>TOTALES</strong>
                    <span></span>
                    <strong class="success-text">Bs ${data.reduce((sum, r) => sum + (r.total_contado || 0), 0).toFixed(2)}</strong>
                    <strong class="warning-text">Bs ${data.reduce((sum, r) => sum + (r.total_credito_pendiente || 0), 0).toFixed(2)}</strong>
                    <strong class="info-text">Bs ${data.reduce((sum, r) => sum + (r.total_credito_pagado || 0), 0).toFixed(2)}</strong>
                    <strong class="total-text">Bs ${data.reduce((sum, r) => sum + (r.total_bs || 0), 0).toFixed(2)}</strong>
                </div>
            </div>
        `;
    }
}

async function enviarRecordatorios() {
    showLoading();
    const result = await fetchAPI('/creditos/recordatorios', { method: 'POST' });
    hideLoading();
    if (result) showToast(`📱 Recordatorios enviados`);
}

// ========== NAVEGACIÓN ==========
function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const tabName = item.dataset.tab;
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            item.classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            if (tabName === 'clientes') cargarClientes();
            if (tabName === 'productos') cargarProductos();
            if (tabName === 'creditos') {
                cargarCreditos();
                cargarClientesHistorial();
                cargarProductosHistorial();
            }
            if (tabName === 'reportes') cargarReportes('semanal');
        });
    });
}

function setupEventListeners() {
    document.getElementById('btn_agregar_cliente')?.addEventListener('click', agregarCliente);
    document.getElementById('btn_agregar_producto')?.addEventListener('click', agregarProducto);
    document.getElementById('btn_agregar_al_carrito')?.addEventListener('click', agregarAlCarrito);
    document.getElementById('btn_registrar_venta_multiple')?.addEventListener('click', registrarVentaMultiple);
    document.getElementById('btn_enviar_recordatorios')?.addEventListener('click', enviarRecordatorios);
    document.getElementById('btn_agregar_producto_historial')?.addEventListener('click', agregarProductoHistorial);
    document.getElementById('btn_guardar_venta_historica')?.addEventListener('click', guardarVentaHistorica);
    document.getElementById('historial_producto')?.addEventListener('change', calcularPreviewHistorial);
    document.getElementById('historial_cantidad')?.addEventListener('input', calcularPreviewHistorial);
    document.getElementById('historial_tasa')?.addEventListener('input', calcularPreviewHistorial);
    document.getElementById('historial_cliente')?.addEventListener('change', calcularPreviewHistorial);
    document.getElementById('cliente_nombre')?.addEventListener('input', buscarClientePorNombre);
    document.getElementById('refreshBtn')?.addEventListener('click', () => {
        cargarTasa();
        cargarProductos();
        cargarClientes();
        cargarCreditos();
        showToast('Actualizado');
    });
    document.querySelectorAll('[data-reporte]').forEach(btn => {
        btn.addEventListener('click', () => {
            cargarReportes(btn.dataset.reporte);
        });
    });
}

// ========== INIT ==========
async function init() {
    await cargarTasa();
    await cargarClientes();
    await cargarProductos();
    await cargarCreditos();
    await cargarClientesHistorial();
    await cargarProductosHistorial();
    setupNavigation();
    setupEventListeners();
    cargarReportes('semanal');
    setInterval(cargarTasa, 300000);
}

document.addEventListener('DOMContentLoaded', init);